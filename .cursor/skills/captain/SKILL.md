---
name: captain
description: >-
  Personal Jira handler (skill name captain) via
  `.cursor/skills/captain/scripts/captain_cli.py`: list boards, open a board,
  get, search, transition, comment, create. Auth is local
  `.cursor/skills/captain/.env` (personal Gmail, vainer-house). Never use
  employer/work Jira or work Jira MCP. Use when the user asks about personal
  Jira boards, captain, or vainer-home tickets.
---
# Captain (personal Jira)

Standalone personal Jira CLI for the home Atlassian site only.

- Site: `https://vainer-house.atlassian.net`
- Auth: gitignored `.cursor/skills/captain/.env` (`CAPTAIN_JIRA_*` only)
- **Ticket language: Hebrew** — summaries and descriptions in Hebrew by default (clear, not overcomplicated)
- Never print `.env` or the API token
- Never call employer/work Jira or work Jira MCP

## Before starting

1. `.cursor/skills/captain/.env` must exist (see `.env.example`).
   Required: `CAPTAIN_JIRA_URL`, `CAPTAIN_JIRA_EMAIL`, `CAPTAIN_JIRA_API_TOKEN`.
2. Python with `jira` + `requests`.
3. CLI: `.cursor/skills/captain/scripts/captain_cli.py`

## Quick start

```bash
python .cursor/skills/captain/scripts/captain_cli.py whoami
python .cursor/skills/captain/scripts/captain_cli.py projects
python .cursor/skills/captain/scripts/captain_cli.py boards
python .cursor/skills/captain/scripts/captain_cli.py board
python .cursor/skills/captain/scripts/captain_cli.py get KEY-123
python .cursor/skills/captain/scripts/captain_cli.py search --jql "status != Done" --max 30
```

## Checklist

- [ ] `whoami` first if auth is unclear.
- [ ] `boards` / `board [id]` to open the personal board.
- [ ] `get KEY` / `search --jql` to read work.
- [ ] `transitions KEY` then `transition KEY --to "..."` (or `--status-emoji`).
- [ ] `comment KEY -m "..."` / `create --summary "..."` (`--project` if unset in `.env`).

Full commands: [reference.md](reference.md).
