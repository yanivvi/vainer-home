# Captain CLI — personal Jira reference

Entrypoint: `.cursor/skills/captain/scripts/captain_cli.py`

Auth: `.cursor/skills/captain/.env` (`CAPTAIN_JIRA_*`). Never print that file or the token.

This skill is **only** for personal Jira (`vainer-house.atlassian.net`). Do not use
employer/work Jira credentials or work Jira MCP.

```bash
python .cursor/skills/captain/scripts/captain_cli.py <subcommand> ...
```

## whoami / projects / boards

```bash
python .cursor/skills/captain/scripts/captain_cli.py whoami
python .cursor/skills/captain/scripts/captain_cli.py projects
python .cursor/skills/captain/scripts/captain_cli.py boards
python .cursor/skills/captain/scripts/captain_cli.py board
python .cursor/skills/captain/scripts/captain_cli.py board 1
python .cursor/skills/captain/scripts/captain_cli.py sprints
python .cursor/skills/captain/scripts/captain_cli.py board-top KEY-1
```

`board` without an id uses `CAPTAIN_JIRA_BOARD_ID`.

## Issues

```bash
python .cursor/skills/captain/scripts/captain_cli.py get KEY-1
python .cursor/skills/captain/scripts/captain_cli.py search --jql "status != Done" --max 30
python .cursor/skills/captain/scripts/captain_cli.py search --jql "assignee = currentUser() AND status != Done"
```

## Transitions

```bash
python .cursor/skills/captain/scripts/captain_cli.py transitions KEY-1
python .cursor/skills/captain/scripts/captain_cli.py transition KEY-1 --to "In Progress"
python .cursor/skills/captain/scripts/captain_cli.py transition KEY-1 --status-emoji "🏗️ In Progress"
python .cursor/skills/captain/scripts/captain_cli.py transition KEY-1 --status-emoji "✅ Done" --dry-run
```

| Emoji status | Transition names tried (first match wins) |
|--------------|-------------------------------------------|
| 🔜 To Do | To Do, Open, Backlog, Start Again |
| 🏗️ In Progress | In Progress, Start Progress, Start, Start Work, Begin Work |
| 👀 In Review | In Review, Review, Code Review, Ready for Review, Submit for Review, Work To Review |
| ✅ Done | Done, Task Done, Resolve, Close, Closed, Complete, Resolved, Finish Work, Passed Review |
| 🚫 Blocked | Blocked, On Hold, Waiting |

## Comments and create

```bash
python .cursor/skills/captain/scripts/captain_cli.py comment KEY-1 -m "Update."
python .cursor/skills/captain/scripts/captain_cli.py create --summary "Something to do" --description "Details" --priority P2
python .cursor/skills/captain/scripts/captain_cli.py tag-summary KEY-1 --group "HOME"
python .cursor/skills/captain/scripts/captain_cli.py update-issue KEY-1 --summary "Exact full title"
```

Default comment prefix: `🤖 [captain]`. Override with `--agent`.

## Common mistakes

- Do not print `.env` or the API token.
- Do not use employer/work Jira or work Jira MCP.
- Do not assume transition names; use `transitions` when `--status-emoji` fails.
