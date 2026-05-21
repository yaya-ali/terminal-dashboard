#!/usr/bin/env python3
"""
Terminal work dashboard.
Single-screen overview: projects / school / freelance / Claude sessions / activity.
Launch: dashboard  (alias in ~/.zshrc)
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

HOME = Path.home()
PROJECTS_DIR = HOME / "projects"
SCHOOL_DIR = HOME / "school"
FREELANCE_DIR = HOME / "freelance"
REFRESH_SECS = 30


# ── Data types ─────────────────────────────────────────────────────────────────

@dataclass
class RepoInfo:
    name: str
    branch: str = "?"
    dirty: bool = False
    last_commit: str = "—"
    week_hours: float = 0.0


@dataclass
class ClaudeSession:
    pid: int
    project: str
    elapsed: str


@dataclass
class FileEntry:
    time_str: str
    project: str
    filename: str


@dataclass
class DashboardData:
    projects: list[RepoInfo] = field(default_factory=list)
    school: list[RepoInfo] = field(default_factory=list)
    freelance: list[RepoInfo] = field(default_factory=list)
    claude: list[ClaudeSession] = field(default_factory=list)
    tmux: list[str] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)
    files: list[FileEntry] = field(default_factory=list)
    refreshed: str = ""


# ── Shell helpers ───────────────────────────────────────────────────────────────

def _sh(cmd: list[str], timeout: int = 5) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


# ── Repo scanning ───────────────────────────────────────────────────────────────

_REPO_SKIP = {"node_modules", ".git", "__pycache__", "dist", ".next", "build",
              ".cache", "venv", "myenv", ".venv", ".turbo", ".pnpm", "reference"}


def _find_repos(base: Path, max_depth: int = 3, max_results: int = 12) -> list[Path]:
    if not base.exists():
        return []
    repos: list[Path] = []

    def _walk(path: Path, depth: int) -> None:
        if depth > max_depth or len(repos) >= max_results:
            return
        try:
            for item in sorted(path.iterdir()):
                if not item.is_dir() or item.name.startswith(".") or item.name in _REPO_SKIP:
                    continue
                if (item / ".git").exists():
                    repos.append(item)
                    if len(repos) >= max_results:
                        return
                else:
                    _walk(item, depth + 1)
        except (PermissionError, OSError):
            pass

    _walk(base, 1)
    return repos


def _repo_info(path: Path) -> RepoInfo:
    branch = _sh(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"]) or "?"
    dirty = bool(_sh(["git", "-C", str(path), "status", "--porcelain"]))
    last = _sh(["git", "-C", str(path), "log", "-1", "--format=%cr"]) or "—"
    monday = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    raw = _sh(["git", "-C", str(path), "log", f"--since={monday}", "--format=%ad", "--date=format:%Y-%m-%d"])
    week_hours = float(len(set(raw.splitlines()))) * 2.0 if raw else 0.0
    return RepoInfo(name=path.name, branch=branch, dirty=dirty, last_commit=last, week_hours=week_hours)


def _scan_area(base: Path) -> list[RepoInfo]:
    return [_repo_info(p) for p in _find_repos(base)]


# ── Claude sessions ─────────────────────────────────────────────────────────────

def _proc_elapsed(pid: str) -> str:
    """Parse ps etime= output: [[DD-]HH:]MM:SS -> human string."""
    raw = _sh(["/bin/ps", "-p", pid, "-o", "etime="]).strip()
    if not raw:
        return "?"
    ints = [int(x) for x in reversed(raw.replace("-", ":").split(":"))]
    secs  = ints[0] if len(ints) > 0 else 0
    mins  = ints[1] if len(ints) > 1 else 0
    hours = ints[2] if len(ints) > 2 else 0
    days  = ints[3] if len(ints) > 3 else 0
    total_h = days * 24 + hours
    if total_h:
        return f"{total_h}h {mins}m"
    return f"{mins}m" if mins else f"{secs}s"


def _proc_cwd_project(pid: str) -> str:
    # -a = AND the filters so we only get the cwd of this specific PID
    raw = _sh(["/usr/sbin/lsof", "-p", pid, "-a", "-d", "cwd", "-Fn"], timeout=3)
    cwd = "?"
    for line in raw.splitlines():
        if line.startswith("n") and line[1:].startswith("/"):
            cwd = line[1:]
            break
    if cwd == "?" or cwd == "/":
        return "?"
    p = Path(cwd)
    if p == HOME:
        return "~"
    for base in [PROJECTS_DIR, SCHOOL_DIR, FREELANCE_DIR]:
        try:
            rel = p.relative_to(base)
            return rel.parts[0] if rel.parts else p.name
        except ValueError:
            continue
    # Fallback: show last 2 path components
    parts = p.parts
    return "/".join(parts[-2:]) if len(parts) >= 2 else p.name


def _scan_claude() -> list[ClaudeSession]:
    raw = _sh(["/bin/ps", "aux"])
    sessions: list[ClaudeSession] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        if "grep" in line or "dashboard.py" in line:
            continue
        parts = line.split(None, 10)
        if len(parts) < 11:
            continue
        cmd = parts[10]
        if "claude" not in cmd.lower():
            continue
        pid = parts[1]
        if pid in seen:
            continue
        seen.add(pid)
        sessions.append(ClaudeSession(
            pid=int(pid),
            project=_proc_cwd_project(pid),
            elapsed=_proc_elapsed(pid),
        ))
    return sessions[:6]


# ── System info ─────────────────────────────────────────────────────────────────

def _scan_tmux() -> list[str]:
    raw = _sh(["tmux", "ls"])
    if not raw or "no server" in raw.lower() or "error" in raw.lower():
        return []
    return raw.splitlines()


def _scan_ports() -> list[str]:
    raw = _sh(["/usr/sbin/lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"], timeout=5)
    ports: set[str] = set()
    for line in raw.splitlines()[1:]:
        cols = line.split()
        if len(cols) >= 9:
            addr = cols[8]
            if ":" in addr:
                port = addr.rsplit(":", 1)[-1]
                if port.isdigit() and int(port) > 1024:
                    ports.add(f":{port}")
    return sorted(ports, key=lambda x: int(x[1:]))[:8]


# ── Recent files ────────────────────────────────────────────────────────────────

_SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", ".next",
              "build", ".cache", "venv", "myenv", ".venv", ".turbo", ".pnpm"}
_WATCH_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".swift", ".md",
               ".ipynb", ".php", ".html", ".css", ".json", ".yaml", ".yml", ".sh"}


def _scan_files() -> list[FileEntry]:
    cutoff = datetime.now() - timedelta(hours=2)
    entries: list[FileEntry] = []
    for base in [PROJECTS_DIR, SCHOOL_DIR, FREELANCE_DIR]:
        if not base.exists():
            continue
        for root, dirs, files in os.walk(str(base)):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
            if root.replace(str(base), "").count(os.sep) > 4:
                dirs.clear()
                continue
            for fname in files:
                if Path(fname).suffix.lower() not in _WATCH_EXTS:
                    continue
                fpath = Path(root) / fname
                try:
                    mt = datetime.fromtimestamp(fpath.stat().st_mtime)
                    if mt < cutoff:
                        continue
                    try:
                        rel = fpath.relative_to(base)
                        proj = rel.parts[0]
                    except ValueError:
                        proj = base.name
                    entries.append(FileEntry(mt.strftime("%H:%M"), proj, fname))
                except OSError:
                    continue
    entries.sort(key=lambda e: e.time_str, reverse=True)
    return entries[:18]


# ── Full data collection (blocking — runs in thread) ────────────────────────────

def collect_all() -> DashboardData:
    return DashboardData(
        projects=_scan_area(PROJECTS_DIR),
        school=_scan_area(SCHOOL_DIR),
        freelance=_scan_area(FREELANCE_DIR),
        claude=_scan_claude(),
        tmux=_scan_tmux(),
        ports=_scan_ports(),
        files=_scan_files(),
        refreshed=datetime.now().strftime("%H:%M:%S"),
    )


# ── Rich markup renderers ────────────────────────────────────────────────────────

def _trunc(s: str, n: int) -> str:
    return (s[: n - 1] + "…") if len(s) > n else s


def _render_repos(title: str, repos: list[RepoInfo]) -> str:
    lines = [f"[bold cyan]{title}[/bold cyan]", ""]
    if not repos:
        lines.append("  [dim]no repos found[/dim]")
    else:
        for r in repos:
            dot = "[red]●[/red]" if r.dirty else "[green]✓[/green]"
            lines.append(
                f"  {dot} [white]{_trunc(r.name, 22):<22}[/white]  [dim]{_trunc(r.last_commit, 14)}[/dim]"
            )
        total = sum(r.week_hours for r in repos)
        lines += ["", f"  [dim]This week: ~{total:.0f}h[/dim]"]
    return "\n".join(lines)


def _render_claude(sessions: list[ClaudeSession]) -> str:
    lines = ["[bold cyan]CLAUDE CODE SESSIONS[/bold cyan]", ""]
    if not sessions:
        lines.append("  [dim]no active Claude sessions detected[/dim]")
    else:
        for s in sessions:
            lines.append(
                f"  [green]▶[/green] [white]{_trunc(s.project, 30):<30}[/white]  "
                f"[yellow]{s.elapsed:>8}[/yellow]  [dim]pid {s.pid}[/dim]"
            )
    return "\n".join(lines)


def _render_infobar(tmux: list[str], ports: list[str], refreshed: str) -> str:
    t = f"tmux: {len(tmux)} session{'s' if len(tmux) != 1 else ''}" if tmux else "tmux: none"
    p = "  ".join(ports) if ports else "none"
    return f"  [dim]{t}[/dim]  [dim]│[/dim]  [dim]ports: {p}[/dim]  [dim]│[/dim]  [dim]↺ {refreshed}[/dim]"


def _render_activity(files: list[FileEntry]) -> str:
    lines = ["[bold cyan]RECENT ACTIVITY[/bold cyan]  [dim](last 2 hours)[/dim]", ""]
    if not files:
        lines.append("  [dim]no file changes in the last 2 hours[/dim]")
    else:
        for f in files:
            lines.append(
                f"  [dim]{f.time_str}[/dim]  [white]{_trunc(f.project, 20):<20}[/white]  "
                f"[cyan]{_trunc(f.filename, 34)}[/cyan]"
            )
    return "\n".join(lines)


# ── Textual widgets ──────────────────────────────────────────────────────────────

class RepoPanel(Static):
    DEFAULT_CSS = """
    RepoPanel {
        border: solid $primary-darken-2;
        height: 100%;
        padding: 0 1;
        overflow-y: auto;
    }
    """


class ClaudePanel(Static):
    DEFAULT_CSS = """
    ClaudePanel {
        border: solid $warning-darken-2;
        padding: 0 1;
        height: auto;
        min-height: 6;
        margin-top: 1;
    }
    """


class InfoBar(Static):
    DEFAULT_CSS = """
    InfoBar {
        background: $surface-darken-1;
        height: 1;
    }
    """


class ActivityPanel(Static):
    DEFAULT_CSS = """
    ActivityPanel {
        border: solid $primary-darken-2;
        padding: 0 1;
        height: 1fr;
        overflow-y: auto;
        margin-top: 1;
    }
    """


# ── App ──────────────────────────────────────────────────────────────────────────

_APP_CSS = """
Screen { layout: vertical; }

#top-row {
    height: 15;
    layout: horizontal;
}
#projects { width: 1fr; }
#school   { width: 1fr; margin: 0 1; }
#freelance { width: 1fr; }
"""


class DashboardApp(App):
    CSS = _APP_CSS
    TITLE = "Dev Dashboard"
    BINDINGS = [
        Binding("r", "do_refresh", "Refresh"),
        Binding("?", "show_help", "Help"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="top-row"):
            yield RepoPanel("  [dim]loading…[/dim]", id="projects")
            yield RepoPanel("  [dim]loading…[/dim]", id="school")
            yield RepoPanel("  [dim]loading…[/dim]", id="freelance")
        yield ClaudePanel("  [dim]loading…[/dim]", id="claude-panel")
        yield InfoBar("", id="infobar")
        yield ActivityPanel("  [dim]loading…[/dim]", id="activity-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()
        self.set_interval(REFRESH_SECS, self._refresh)

    @work(exclusive=True)
    async def _refresh(self) -> None:
        data = await asyncio.to_thread(collect_all)
        self.query_one("#projects",      RepoPanel).update(_render_repos("PROJECTS", data.projects))
        self.query_one("#school",        RepoPanel).update(_render_repos("SCHOOL",   data.school))
        self.query_one("#freelance",     RepoPanel).update(_render_repos("FREELANCE", data.freelance))
        self.query_one("#claude-panel",  ClaudePanel).update(_render_claude(data.claude))
        self.query_one("#infobar",       InfoBar).update(_render_infobar(data.tmux, data.ports, data.refreshed))
        self.query_one("#activity-panel",ActivityPanel).update(_render_activity(data.files))

    def action_do_refresh(self) -> None:
        self.query_one("#infobar", InfoBar).update("  [dim]refreshing…[/dim]")
        self._refresh()

    def action_show_help(self) -> None:
        self.notify(
            "r  = manual refresh\n"
            "q  = quit\n"
            "Auto-refreshes every 30 seconds.\n"
            "Hours = unique commit-days this week × 2h.",
            title="Help",
            timeout=7,
        )


if __name__ == "__main__":
    DashboardApp().run()
