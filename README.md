# vainer-home

Personal home workspace: apartment work transcripts and a Cursor skill (`captain`) for the personal Atlassian site (`vainer-house`).

Nothing in this repo is employer/work property. Secrets stay out of git.

## What’s here

| Path | Purpose |
|------|---------|
| `.cursor/skills/captain/` | Cursor skill + CLI for personal Jira |
| `transcripts/` | Home walkthrough transcripts (e.g. WhatsApp → Whisper) |
| `requirements.txt` | Python deps for the captain CLI |

## Setup (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .cursor/skills/captain/.env.example .cursor/skills/captain/.env
# edit .env — never commit it
```

Quick check:

```bash
python .cursor/skills/captain/scripts/captain_cli.py whoami
python .cursor/skills/captain/scripts/captain_cli.py boards
```

## Environment

Local file: `.cursor/skills/captain/.env` (gitignored). Same names work as process env / CI secrets.

| Variable | Required | Notes |
|----------|----------|--------|
| `CAPTAIN_JIRA_URL` | yes | Site URL, e.g. `https://vainer-house.atlassian.net` |
| `CAPTAIN_JIRA_EMAIL` | yes | Atlassian account email for the API token |
| `CAPTAIN_JIRA_API_TOKEN` | yes | [Atlassian API token](https://id.atlassian.com/manage-profile/security/api-tokens) — treat as secret |
| `CAPTAIN_JIRA_PROJECT` | no | Default project key for `create` |
| `CAPTAIN_JIRA_BOARD_ID` | no | Default board id for `board` |

Optional override path: `CAPTAIN_ENV_FILE=/path/to/.env`.

## GitHub (remote-ready)

Repo is public — put credentials in **Secrets**, not in the README or committed files.

**Recommended Secrets** (Settings → Secrets and variables → Actions → Secrets):

- `CAPTAIN_JIRA_API_TOKEN` — secret
- `CAPTAIN_JIRA_EMAIL` — secret (account email)

**Recommended Variables** (Actions → Variables) — non-secret config:

- `CAPTAIN_JIRA_URL`
- `CAPTAIN_JIRA_PROJECT`
- `CAPTAIN_JIRA_BOARD_ID`

In GitHub Actions, map them into the job env, for example:

```yaml
env:
  CAPTAIN_JIRA_URL: ${{ vars.CAPTAIN_JIRA_URL }}
  CAPTAIN_JIRA_EMAIL: ${{ secrets.CAPTAIN_JIRA_EMAIL }}
  CAPTAIN_JIRA_API_TOKEN: ${{ secrets.CAPTAIN_JIRA_API_TOKEN }}
  CAPTAIN_JIRA_PROJECT: ${{ vars.CAPTAIN_JIRA_PROJECT }}
  CAPTAIN_JIRA_BOARD_ID: ${{ vars.CAPTAIN_JIRA_BOARD_ID }}
```

The CLI already prefers real environment variables over `.env`, so the same commands work in CI once those are set.

## Safety

- Never commit `.env`, tokens, or `.pem` files
- Do not reuse employer/work Jira credentials here
- Do not print `CAPTAIN_JIRA_API_TOKEN`
