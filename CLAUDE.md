# terminal-dashboard — Claude Project

## What this is

A single-file Textual TUI that gives a developer a zero-friction morning
stand-up with themselves. One screen, auto-refreshing every 30 s:

- **Three repo panels** (Projects / School / Freelance) — dirty flag, branch, last commit, estimated weekly hours
- **Claude Code sessions** — active `claude` processes with project name and elapsed time
- **Info bar** — tmux sessions + listening TCP ports + last refresh time
- **Recent Activity** — files touched in the last 2 hours across all work areas

GitHub: https://github.com/yaya-ali/terminal-dashboard (public, MIT)

---

## File layout

```
terminal-dashboard/
├── dashboard.py       # entire app — scanning, rendering, Textual UI
├── requirements.txt   # textual>=0.47.0, rich>=13.0.0
├── README.md
├── LICENSE
└── CLAUDE.md          # ← this file
```

Everything lives in `dashboard.py`. No config file yet (planned).

---

## Running

```bash
python3 dashboard.py
# or, if alias is set up:
dashboard
```

Key bindings: `r` refresh · `q` quit · `?` help

---

## Architecture

```
dashboard.py
├── Data layer  (pure functions, run in asyncio.to_thread)
│   ├── _find_repos / _repo_info / _scan_area   — git repo scanning
│   ├── _scan_claude                             — ps aux → lsof cwd
│   ├── _scan_tmux / _scan_ports                — system info
│   ├── _scan_files                             — recent mtime walk
│   └── collect_all()                           — assembles DashboardData
├── Render layer  (Rich markup strings)
│   ├── _render_repos / _render_claude
│   ├── _render_infobar / _render_activity
│   └── _trunc helper
└── Textual UI
    ├── RepoPanel / ClaudePanel / InfoBar / ActivityPanel  — Static subclasses
    └── DashboardApp                             — main App, 30s interval worker
```

Key constants at the top of `dashboard.py`:

```python
PROJECTS_DIR  = HOME / "projects"
SCHOOL_DIR    = HOME / "school"
FREELANCE_DIR = HOME / "freelance"
REFRESH_SECS  = 30
```

---

## Dev workflow

```bash
# install deps
pip install -r requirements.txt

# run
python3 dashboard.py

# no test suite yet (planned)
```

No build step. Single file — edit and re-run.

---

## Roadmap (open issues / PRs welcome)

- [ ] `~/.config/terminal-dashboard/config.toml` — configurable paths, refresh rate
- [ ] Click a repo row → open in `$EDITOR` or `$TERMINAL` at that path
- [ ] Filter / fuzzy-search repos by name
- [ ] GitHub API panel — open PRs / issues per repo
- [ ] Extra scan areas (dotfiles, custom paths)
- [ ] CPU / memory / disk mini-panel
- [ ] Stale-repo warning (dirty + last commit > N days)
- [ ] Test suite (pytest + Textual pilot)
- [ ] Screenshot / GIF in README

---

## Agent instructions (for the future custom agent)

When an agent works on this project it should:

1. **Never hard-code paths** — always use `Path.home()` or constants already defined at the top of `dashboard.py`.
2. **Keep it single-file** until a config file is introduced; resist splitting prematurely.
3. **Run the app** (`python3 dashboard.py`) to verify UI changes — type checking alone is not enough.
4. **Update README.md** in the same commit as any user-visible change.
5. **Update the Roadmap** in this file and in README.md when a roadmap item is completed.
6. **Commit style**: `feat:`, `fix:`, `chore:` prefixes; keep messages short.
7. **Never commit**: `__pycache__/`, `.DS_Store`, personal paths, API keys.
