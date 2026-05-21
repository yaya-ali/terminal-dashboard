# terminal-dashboard

A single-screen terminal dashboard for developers who juggle multiple projects, school work, and freelance at the same time.

Built with [Textual](https://github.com/Textualize/textual) — renders entirely in the terminal, no browser needed.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

---

## What it does

At a glance, one keypress away:

| Panel | What you see |
|---|---|
| **Projects / School / Freelance** | Every git repo in those directories — branch, dirty flag, last commit time, estimated hours this week |
| **Claude Code Sessions** | Any active `claude` processes — project name, elapsed time, PID |
| **Info bar** | Live tmux sessions + listening TCP ports + last refresh timestamp |
| **Recent Activity** | Files you've touched in the last 2 hours across all your work areas |

Auto-refreshes every 30 seconds. Press `r` to force a refresh, `q` to quit.

---

## Goal

Most developer dashboards live in a browser tab you forget to open. This one launches in under a second from your terminal, shows exactly what you need when you sit down to work, and gets out of the way.

The goal is a **zero-friction morning stand-up with yourself**: what's dirty, what changed recently, what's running.

---

## Implementation

```
terminal-dashboard/
├── dashboard.py      # single-file app — all scanning, rendering, and UI
└── requirements.txt
```

**Stack:**
- [`textual`](https://github.com/Textualize/textual) — TUI framework (reactive layout, async workers)
- [`rich`](https://github.com/Textualize/rich) — markup rendering inside Textual panels

**How it scans:**
- Walks `~/projects`, `~/school`, `~/freelance` up to 3 levels deep, skipping common noise dirs (`node_modules`, `.next`, `dist`, etc.)
- Calls `git` subprocess per repo for branch/dirty/last-commit/week-hours (week-hours = unique commit-days this week × 2h estimate)
- Detects Claude Code sessions via `ps aux` + resolves their working directory with `lsof`
- Recent activity uses `os.walk` + `stat.st_mtime` — no inotify/FSEvents dependency

All scanning runs in a thread (`asyncio.to_thread`) so the UI never blocks.

---

## Install

```bash
git clone https://github.com/yaya-ali/terminal-dashboard.git
cd terminal-dashboard
pip install -r requirements.txt
python3 dashboard.py
```

**Optional — add a shell alias:**

```bash
# in ~/.zshrc or ~/.bashrc
alias dashboard="python3 ~/projects/terminal-dashboard/dashboard.py"
```

Then just type `dashboard` from anywhere.

---

## Configuration

Edit the constants at the top of `dashboard.py` to match your layout:

```python
PROJECTS_DIR = HOME / "projects"   # change to your projects folder
SCHOOL_DIR   = HOME / "school"     # remove or point elsewhere
FREELANCE_DIR = HOME / "freelance" # same
REFRESH_SECS = 30                  # auto-refresh interval
```

---

## Roadmap / Contributing

This is an early, single-file tool — contributions are very welcome.

Ideas for what's next:

- [ ] Config file (`~/.config/terminal-dashboard/config.toml`) so paths don't require editing source
- [ ] Click a repo row to open it in your editor
- [ ] Filter / search repos by name
- [ ] Show open PRs / issues count (GitHub API)
- [ ] More work-area panels (e.g. `~/dotfiles`, custom paths)
- [ ] CPU / memory / disk mini-panel
- [ ] Notification on dirty repos older than N days

**To contribute:**
1. Fork the repo
2. Create a branch (`git checkout -b feature/my-idea`)
3. Make your changes in `dashboard.py`
4. Open a PR with a short description of what it does

No setup beyond `pip install -r requirements.txt`. The whole app is one file — easy to read and easy to extend.

---

## License

MIT
