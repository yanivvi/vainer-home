#!/usr/bin/env python3
"""
Captain CLI: personal Jira boards, issues, transitions, comments.

Auth is loaded from `.cursor/skills/captain/.env` (see .env.example).
Never print tokens, passwords, or the .env file.
Never use work Jira credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Optional, Tuple

import requests
from jira import JIRA
from jira.exceptions import JIRAError

from _env import load_dotenv, require_env

JIRA_TRANSITION_MAP = {
    "🔜 To Do": ["To Do", "Open", "Backlog", "Start Again"],
    "🏗️ In Progress": [
        "In Progress",
        "Start Progress",
        "Start",
        "Start Work",
        "Begin Work",
    ],
    "👀 In Review": [
        "In Review",
        "Review",
        "Code Review",
        "Ready for Review",
        "Submit for Review",
        "Work To Review",
    ],
    "✅ Done": [
        "Done",
        "Task Done",
        "Resolve",
        "Close",
        "Closed",
        "Complete",
        "Resolved",
        "Finish Work",
        "Passed Review",
    ],
    "🚫 Blocked": ["Blocked", "On Hold", "Waiting"],
}

DEFAULT_AGENT = "captain"


class JiraConfig:
    def __init__(self) -> None:
        env_file = load_dotenv()
        self.url = require_env("CAPTAIN_JIRA_URL", env_file=env_file).rstrip("/")
        self.email = require_env("CAPTAIN_JIRA_EMAIL", env_file=env_file)
        self.token = require_env("CAPTAIN_JIRA_API_TOKEN", env_file=env_file)
        self.project = (os.environ.get("CAPTAIN_JIRA_PROJECT") or "").strip() or None
        board_raw = (os.environ.get("CAPTAIN_JIRA_BOARD_ID") or "").strip()
        self.board_id = int(board_raw) if board_raw else None

    @property
    def auth(self) -> Tuple[str, str]:
        return self.email, self.token


CONFIG: Optional[JiraConfig] = None


def get_config() -> JiraConfig:
    global CONFIG
    if CONFIG is None:
        CONFIG = JiraConfig()
    return CONFIG


def get_jira_client() -> JIRA:
    cfg = get_config()
    return JIRA(server=cfg.url, basic_auth=cfg.auth)


def _agile_get(path: str, params: Optional[dict] = None) -> dict:
    cfg = get_config()
    session = requests.Session()
    session.auth = cfg.auth
    response = session.get(
        f"{cfg.url}/rest/agile/1.0/{path}",
        params=params or {},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _agile_put(path: str, payload: dict) -> None:
    cfg = get_config()
    session = requests.Session()
    session.auth = cfg.auth
    response = session.put(
        f"{cfg.url}/rest/agile/1.0/{path}",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()


def get_agent_prefix(agent_name: Optional[str]) -> str:
    name = agent_name or DEFAULT_AGENT
    return f"🤖 [{name}]"


def _format_description(desc) -> str:
    if not desc:
        return "(none)"
    if isinstance(desc, str):
        return desc[:4000] + ("…" if len(desc) > 4000 else "")
    return str(desc)[:800] + ("…" if len(str(desc)) > 800 else "")


def _http_error_message(exc: Exception) -> str:
    status = None
    if isinstance(exc, JIRAError):
        status = exc.status_code
    elif isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
    if status in (401, 403):
        return (
            f"Jira auth failed (HTTP {status}). "
            "Check CAPTAIN_JIRA_EMAIL (must be the Atlassian account that created the token) "
            "and CAPTAIN_JIRA_API_TOKEN in .env. Do not print the token."
        )
    if status:
        return f"Jira HTTP {status}"
    return str(exc)


def cmd_whoami(client: JIRA) -> None:
    cfg = get_config()
    me = client.myself()
    print(f"User:    {me.get('displayName', '—')}")
    print(f"Account: {me.get('accountId', '—')}")
    print(f"Site:    {cfg.url}")
    print(f"Project: {cfg.project or '(unset — run projects)'}")
    if cfg.board_id:
        print(f"Board:   {cfg.board_id}")


def cmd_projects(client: JIRA) -> None:
    projects = client.projects()
    if not projects:
        print("No projects found.")
        return
    print(f"{'Key':<12} Name")
    print("-" * 50)
    for project in projects:
        print(f"{project.key:<12} {project.name}")


def cmd_boards(name: Optional[str], project: Optional[str], max_results: int) -> None:
    params: dict = {"maxResults": max_results}
    if name:
        params["name"] = name
    if project:
        params["projectKeyOrId"] = project.upper()
    data = _agile_get("board", params)
    values = data.get("values") or []
    if not values:
        print("No boards found.")
        return
    print(f"{'ID':<8} {'Type':<10} {'Project':<10} Name")
    print("-" * 80)
    for board in values:
        loc = board.get("location") or {}
        proj = loc.get("projectKey") or loc.get("projectName") or "—"
        print(
            f"{board.get('id', '—'):<8} "
            f"{str(board.get('type') or '—')[:10]:<10} "
            f"{str(proj)[:10]:<10} "
            f"{board.get('name', '')}"
        )
    total = data.get("total")
    if total and total > len(values):
        print(f"\nShowing {len(values)} of {total}. Raise --max to see more.")


def cmd_board(board_id: int, max_results: int, jql: Optional[str]) -> None:
    cfg = get_config()
    meta = _agile_get(f"board/{board_id}")
    loc = meta.get("location") or {}
    proj = loc.get("projectKey") or loc.get("projectName") or "—"
    print(f"Board:   {meta.get('name')} (id={board_id}, type={meta.get('type')})")
    print(f"Project: {proj}")
    print(f"URL:     {cfg.url}/jira/software/projects/{proj}/boards/{board_id}")
    print()

    params: dict = {"maxResults": max_results}
    if jql:
        params["jql"] = jql
    data = _agile_get(f"board/{board_id}/issue", params)
    issues = data.get("issues") or []
    if not issues:
        print("No issues on this board.")
        return

    by_status: dict[str, list] = defaultdict(list)
    for issue in issues:
        fields = issue.get("fields") or {}
        status = ((fields.get("status") or {}).get("name")) or "Unknown"
        by_status[status].append(issue)

    for status, group in by_status.items():
        print(f"## {status} ({len(group)})")
        for issue in group:
            fields = issue.get("fields") or {}
            key = issue.get("key")
            summary = (fields.get("summary") or "")[:70]
            assignee = fields.get("assignee") or {}
            who = assignee.get("displayName") if assignee else "Unassigned"
            print(f"  {key:<12} {who:<22} {summary}")
        print()
    total = data.get("total") or len(issues)
    if total > len(issues):
        print(f"Showing {len(issues)} of {total}. Raise --max to see more.")


def cmd_sprints(board_id: int, state: str) -> None:
    data = _agile_get(f"board/{board_id}/sprint", {"state": state, "maxResults": 50})
    values = data.get("values") or []
    if not values:
        print("No sprints found (board may be Kanban).")
        return
    print(f"{'ID':<8} {'State':<10} Name")
    print("-" * 60)
    for sprint in values:
        print(
            f"{sprint.get('id', '—'):<8} "
            f"{str(sprint.get('state') or '—')[:10]:<10} "
            f"{sprint.get('name', '')}"
        )


def cmd_get(client: JIRA, issue_key: str) -> None:
    cfg = get_config()
    issue = client.issue(
        issue_key,
        fields="summary,status,priority,assignee,reporter,created,description",
    )
    f = issue.fields
    pr = f.priority.name if f.priority else "—"
    assignee = f.assignee.displayName if f.assignee else "Unassigned"
    reporter = f.reporter.displayName if f.reporter else "—"
    created = f.created[:10] if f.created else "—"
    print(f"Key:       {issue.key}")
    print(f"URL:       {cfg.url}/browse/{issue.key}")
    print(f"Summary:   {f.summary}")
    print(f"Status:    {f.status.name}")
    print(f"Priority:  {pr}")
    print(f"Assignee:  {assignee}")
    print(f"Reporter:  {reporter}")
    print(f"Created:   {created}")
    print(f"Description:\n{_format_description(f.description)}")


def cmd_search(client: JIRA, jql: str, max_results: int) -> None:
    issues = client.search_issues(jql, maxResults=max_results)
    if not issues:
        print("No issues matched.")
        return
    print(f"{'Key':<12} {'Status':<22} {'Prio':<10} Summary")
    print("-" * 100)
    for issue in issues:
        st = issue.fields.status.name[:20]
        pr = issue.fields.priority.name if issue.fields.priority else "—"
        sm = (issue.fields.summary or "")[:55]
        if len(issue.fields.summary or "") > 55:
            sm += "…"
        print(f"{issue.key:<12} {st:<22} {pr:<10} {sm}")


def get_available_transitions(client: JIRA, issue_key: str) -> list[Tuple[str, str]]:
    issue = client.issue(issue_key)
    transitions = client.transitions(issue)
    return [(t["id"], t["name"]) for t in transitions]


def cmd_transitions(client: JIRA, issue_key: str) -> None:
    available = get_available_transitions(client, issue_key)
    issue = client.issue(issue_key, fields="status,summary")
    summary = issue.fields.summary or ""
    head = f"{issue_key}: {summary[:70]}…" if len(summary) > 70 else f"{issue_key}: {summary}"
    print(head)
    print(f"Current status: {issue.fields.status.name}")
    print("Available transitions:")
    for _, name in available:
        print(f"  - {name}")


def pick_transition_id(
    available: list[Tuple[str, str]],
    transition_to: Optional[str],
    status_emoji: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    if transition_to:
        target = transition_to.strip()
        for tid, tname in available:
            if tname == target or tname.lower() == target.lower():
                return tid, tname
        tlower = target.lower()
        for tid, tname in available:
            if tlower in tname.lower() or tname.lower() in tlower:
                return tid, tname
        return None, None

    if status_emoji:
        target_names = JIRA_TRANSITION_MAP.get(status_emoji.strip(), [])
        lowered = [n.lower() for n in target_names]
        for tid, tname in available:
            if tname in target_names or tname.lower() in lowered:
                return tid, tname
        return None, None

    return None, None


def cmd_transition(
    client: JIRA,
    issue_key: str,
    transition_to: Optional[str],
    status_emoji: Optional[str],
    branch: Optional[str],
    pr: Optional[str],
    agent_name: Optional[str],
    dry_run: bool,
    no_comment: bool,
) -> int:
    issue = client.issue(issue_key)
    current = issue.fields.status.name
    available = get_available_transitions(client, issue_key)
    tid, tname = pick_transition_id(available, transition_to, status_emoji)

    print(f"{issue_key}: Jira status = '{current}'")
    print(f"   Available: {[n for _, n in available]}")

    if not tid:
        want = transition_to or status_emoji
        print(f"   ❌ No matching transition for: {want!r}")
        return 1

    if dry_run:
        print(f"   🔍 DRY RUN: would use transition '{tname}' (id={tid})")
        return 0

    client.transition_issue(issue, tid)
    print(f"   ✅ Transitioned via '{tname}'")

    if not no_comment:
        agent_prefix = get_agent_prefix(agent_name)
        label = status_emoji or tname
        parts = [f"{agent_prefix} Status: {label}"]
        if branch:
            parts.append(f"Branch: {branch}")
        if pr:
            parts.append(f"PR: {pr}")
        comment = " | ".join(parts)
        client.add_comment(issue_key, comment)
        print("   💬 Comment added")

    issue = client.issue(issue_key, fields="status")
    print(f"   📋 Jira status is now: '{issue.fields.status.name}'")
    return 0


def cmd_comment(client: JIRA, issue_key: str, message: str, agent_name: Optional[str]) -> None:
    prefix = get_agent_prefix(agent_name)
    body = f"{prefix} {message}"
    client.add_comment(issue_key, body)
    print(f"✅ Comment added to {issue_key}")


def cmd_delete(client: JIRA, issue_key: str, delete_subtasks: bool, dry_run: bool) -> int:
    issue_key = issue_key.upper()
    if dry_run:
        print(f"🔍 DRY RUN: would delete {issue_key} (deleteSubtasks={delete_subtasks})")
        return 0
    issue = client.issue(issue_key)
    issue.delete(deleteSubtasks=delete_subtasks)
    print(f"✅ Deleted {issue_key}")
    return 0


def _p_to_jira_priority(p: str) -> str:
    return {"P0": "Highest", "P1": "High", "P2": "Medium", "P3": "Low"}.get(p, "Medium")


def apply_summary_group_tag(group: str, summary: str) -> str:
    label = (group or "").strip()
    body = (summary or "").strip()
    if not label:
        return body
    return f"[{label}] {body}"


def cmd_tag_summary(client: JIRA, issue_key: str, group: str, force: bool) -> int:
    issue = client.issue(issue_key, fields="summary")
    current = (issue.fields.summary or "").strip()
    if current.startswith("[") and not force:
        print(
            "Summary already starts with '['; refusing to nest tags. "
            "Use --force to prepend anyway."
        )
        return 1
    issue.update(fields={"summary": apply_summary_group_tag(group, current)})
    print(f"✅ Updated {issue_key} summary (group tag: [{group.strip()}] …)")
    return 0


def cmd_update_issue(
    client: JIRA,
    issue_key: str,
    summary: Optional[str],
    description: Optional[str],
) -> int:
    if summary is None and description is None:
        print("Provide at least one of --summary or --description.")
        return 1
    fields: dict = {}
    if summary is not None:
        fields["summary"] = summary
    if description is not None:
        fields["description"] = description
    issue = client.issue(issue_key)
    issue.update(fields=fields)
    print(f"✅ Updated {issue_key}: {', '.join(fields.keys())}")
    return 0


def _issue_on_board(board_id: int, issue_key: str) -> bool:
    data = _agile_get(
        f"board/{board_id}/issue",
        {"jql": f"key = {issue_key}", "maxResults": 1},
    )
    return data.get("total", 0) > 0


def _issue_in_backlog(board_id: int, issue_key: str) -> bool:
    data = _agile_get(
        f"board/{board_id}/backlog",
        {"jql": f"key = {issue_key}", "maxResults": 1},
    )
    return data.get("total", 0) > 0


def _top_open_board_issue(client: JIRA, project: str) -> Optional[str]:
    issues = client.search_issues(
        f"project = {project} AND status != Done ORDER BY rank ASC",
        maxResults=1,
    )
    return issues[0].key if issues else None


def cmd_board_top(
    client: JIRA,
    issue_key: str,
    board_id: int,
    project: str,
    dry_run: bool,
) -> int:
    issue_key = issue_key.upper()
    on_board = _issue_on_board(board_id, issue_key)
    in_backlog = _issue_in_backlog(board_id, issue_key)
    location = "board" if on_board else ("backlog" if in_backlog else "unknown")

    top_key = _top_open_board_issue(client, project)
    if top_key == issue_key:
        print(f"{issue_key}: already top-ranked open issue (location={location})")
        return 0

    payload: dict = {"issues": [issue_key]}
    if top_key:
        payload["rankBeforeIssue"] = top_key

    print(f"{issue_key}: location={location} board_id={board_id}")
    if top_key:
        print(f"   Will rank before {top_key} (top of open board)")
    else:
        print("   No open issues on board; ranking issue alone")

    if dry_run:
        print(f"   🔍 DRY RUN: would PUT issue/rank {json.dumps(payload)}")
        return 0

    _agile_put("issue/rank", payload)
    on_board_after = _issue_on_board(board_id, issue_key)
    print(f"   ✅ Ranked on board (on_board={on_board_after})")
    return 0


def cmd_create(
    client: JIRA,
    project: str,
    issue_type: str,
    summary: str,
    description: str,
    priority_p: Optional[str],
    group: Optional[str],
    parent: Optional[str] = None,
) -> None:
    cfg = get_config()
    fields: dict = {
        "project": {"key": project},
        "summary": apply_summary_group_tag(group, summary) if group else summary,
        "issuetype": {"name": issue_type},
    }
    if description:
        fields["description"] = description
    if priority_p:
        fields["priority"] = {"name": _p_to_jira_priority(priority_p)}
    if parent:
        fields["parent"] = {"key": parent.upper()}
    new_issue = client.create_issue(fields=fields)
    key = new_issue.key
    print(f"✅ Created {key}")
    print(f"   {cfg.url}/browse/{key}")
    if parent:
        print(f"   parent: {parent.upper()}")


def _default_board_id() -> int:
    cfg = get_config()
    if cfg.board_id is None:
        raise SystemExit("Set CAPTAIN_JIRA_BOARD_ID in .env or pass --board-id.")
    return cfg.board_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Captain personal Jira CLI. Auth via local .env (never printed)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("whoami", help="Verify auth and print the connected user")
    sub.add_parser("projects", help="List projects on the personal site")

    p_boards = sub.add_parser("boards", help="List boards")
    p_boards.add_argument("--name", help="Filter by board name")
    p_boards.add_argument("--project", help="Filter by project key")
    p_boards.add_argument("--max", type=int, default=50, help="Max results (default 50)")

    p_board = sub.add_parser("board", help="Show issues on a board, grouped by status")
    p_board.add_argument(
        "board_id",
        nargs="?",
        type=int,
        help="Board id (default: CAPTAIN_JIRA_BOARD_ID from .env)",
    )
    p_board.add_argument("--jql", help="Extra JQL filter on the board")
    p_board.add_argument("--max", type=int, default=50, help="Max results (default 50)")

    p_sprints = sub.add_parser("sprints", help="List sprints on a board")
    p_sprints.add_argument(
        "board_id",
        nargs="?",
        type=int,
        help="Board id (default: CAPTAIN_JIRA_BOARD_ID from .env)",
    )
    p_sprints.add_argument(
        "--state",
        default="active,future",
        help="Sprint states (default active,future)",
    )

    p_get = sub.add_parser("get", help="Print issue details")
    p_get.add_argument("issue", help="Issue key, e.g. HOME-1")

    p_search = sub.add_parser("search", help="Run JQL and list issues")
    p_search.add_argument("--jql", required=True, help="JQL query")
    p_search.add_argument("--max", type=int, default=50, help="Max results (default 50)")

    p_tr = sub.add_parser("transitions", help="List available transitions")
    p_tr.add_argument("issue")

    p_trans = sub.add_parser("transition", help="Transition an issue")
    p_trans.add_argument("issue")
    g = p_trans.add_mutually_exclusive_group(required=True)
    g.add_argument("--to", metavar="NAME", help="Transition name")
    g.add_argument(
        "--status-emoji",
        metavar="EMOJI_STATUS",
        help='Team status emoji label, e.g. "🏗️ In Progress"',
    )
    p_trans.add_argument("--branch", help="Recorded in the auto-comment")
    p_trans.add_argument("--pr", help="PR URL recorded in the auto-comment")
    p_trans.add_argument("--agent", help="Subagent slug for comment prefix")
    p_trans.add_argument(
        "--no-comment",
        action="store_true",
        help="Do not add an agent comment after transitioning",
    )
    p_trans.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which transition would run; do not change Jira",
    )

    p_comm = sub.add_parser("comment", help="Add a comment")
    p_comm.add_argument("issue")
    p_comm.add_argument("-m", "--message", required=True)
    p_comm.add_argument("--agent", help="Subagent slug for prefix")

    p_del = sub.add_parser("delete", help="Delete an issue")
    p_del.add_argument("issue")
    p_del.add_argument(
        "--subtasks",
        action="store_true",
        help="Also delete subtasks (required if the issue has any)",
    )
    p_del.add_argument("--dry-run", action="store_true")

    p_create = sub.add_parser("create", help="Create a new issue")
    p_create.add_argument("--project", default=None, help="Project key (default: CAPTAIN_JIRA_PROJECT)")
    p_create.add_argument(
        "--type",
        dest="issue_type",
        default="Task",
        metavar="TYPE",
        help="Issue type in Jira (default: Task)",
    )
    p_create.add_argument("--summary", required=True)
    p_create.add_argument("--description", default="", help="Plain text description")
    p_create.add_argument(
        "--group",
        metavar="LABEL",
                help='Prepend [LABEL] to the summary, e.g. --group "HOME"',
    )
    p_create.add_argument(
        "--priority",
        choices=["P0", "P1", "P2", "P3"],
        help="Maps to Jira priority names",
    )
    p_create.add_argument(
        "--parent",
        metavar="KEY",
        help="Parent issue key (required for Subtask)",
    )

    p_tag_s = sub.add_parser("tag-summary", help="Prepend [Group] to an existing summary")
    p_tag_s.add_argument("issue")
    p_tag_s.add_argument("--group", required=True, metavar="LABEL")
    p_tag_s.add_argument("--force", action="store_true")

    p_upd = sub.add_parser("update-issue", help="Set summary and/or description")
    p_upd.add_argument("issue")
    p_upd.add_argument("--summary")
    p_upd.add_argument("--description")

    p_board_top = sub.add_parser(
        "board-top",
        help="Rank issue to top of board (moves backlog → board)",
    )
    p_board_top.add_argument("issue")
    p_board_top.add_argument("--board-id", type=int, default=None)
    p_board_top.add_argument("--project", default=None)
    p_board_top.add_argument("--dry-run", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        print("🔐 Connecting to Jira...")
        client = get_jira_client()
        cfg = get_config()

        if args.command == "whoami":
            cmd_whoami(client)
        elif args.command == "projects":
            cmd_projects(client)
        elif args.command == "boards":
            cmd_boards(args.name, args.project, args.max)
        elif args.command == "board":
            board_id = args.board_id if args.board_id is not None else _default_board_id()
            cmd_board(board_id, args.max, args.jql)
        elif args.command == "sprints":
            board_id = args.board_id if args.board_id is not None else _default_board_id()
            cmd_sprints(board_id, args.state)
        elif args.command == "get":
            cmd_get(client, args.issue.upper())
        elif args.command == "search":
            cmd_search(client, args.jql, args.max)
        elif args.command == "transitions":
            cmd_transitions(client, args.issue.upper())
        elif args.command == "transition":
            return cmd_transition(
                client,
                args.issue.upper(),
                args.to,
                args.status_emoji,
                args.branch,
                args.pr,
                args.agent,
                args.dry_run,
                args.no_comment,
            )
        elif args.command == "comment":
            cmd_comment(client, args.issue.upper(), args.message, args.agent)
        elif args.command == "delete":
            return cmd_delete(client, args.issue, args.subtasks, args.dry_run)
        elif args.command == "create":
            project = (args.project or cfg.project or "").upper()
            if not project:
                raise SystemExit("Set CAPTAIN_JIRA_PROJECT in .env or pass --project.")
            cmd_create(
                client,
                project,
                args.issue_type,
                args.summary,
                args.description,
                args.priority,
                getattr(args, "group", None),
                getattr(args, "parent", None),
            )
        elif args.command == "tag-summary":
            return cmd_tag_summary(client, args.issue.upper(), args.group, args.force)
        elif args.command == "update-issue":
            return cmd_update_issue(
                client, args.issue.upper(), args.summary, args.description
            )
        elif args.command == "board-top":
            board_id = args.board_id if args.board_id is not None else _default_board_id()
            project = (args.project or cfg.project or "").upper()
            if not project:
                raise SystemExit("Set CAPTAIN_JIRA_PROJECT in .env or pass --project.")
            return cmd_board_top(
                client, args.issue.upper(), board_id, project, args.dry_run
            )
        else:
            parser.print_help()
            return 1
        return 0
    except (requests.HTTPError, JIRAError) as exc:
        print(f"❌ {_http_error_message(exc)}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
