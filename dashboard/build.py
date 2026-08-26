#!/usr/bin/env python3
"""Build dashboard/index.html from personal Jira (captain .env)."""

from __future__ import annotations

import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".cursor" / "skills" / "captain" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _env import load_dotenv, require_env  # noqa: E402
from jira import JIRA  # noqa: E402

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


def is_done(status: str) -> bool:
    return status == "Done"


def is_ip(status: str) -> bool:
    return status == "In Progress"


def fetch() -> dict:
    env = load_dotenv()
    url = require_env("CAPTAIN_JIRA_URL", env_file=env).rstrip("/")
    email = require_env("CAPTAIN_JIRA_EMAIL", env_file=env)
    token = require_env("CAPTAIN_JIRA_API_TOKEN", env_file=env)
    jira = JIRA(server=url, basic_auth=(email, token))
    fields = "summary,status,assignee,issuetype,parent,priority"
    epics = jira.search_issues(
        "project = CAPTAIN AND issuetype = Epic ORDER BY key",
        maxResults=50,
        fields=fields,
    )
    issues = jira.search_issues(
        "project = CAPTAIN AND issuetype != Epic ORDER BY key",
        maxResults=200,
        fields=fields,
    )
    return {
        "site": url,
        "epics": [
            {
                "key": e.key,
                "summary": e.fields.summary,
                "status": e.fields.status.name,
                "assignee": e.fields.assignee.displayName if e.fields.assignee else None,
            }
            for e in epics
        ],
        "issues": [
            {
                "key": i.key,
                "summary": i.fields.summary,
                "status": i.fields.status.name,
                "assignee": i.fields.assignee.displayName if i.fields.assignee else "Unassigned",
                "parent": i.fields.parent.key if getattr(i.fields, "parent", None) else None,
                "priority": i.fields.priority.name if i.fields.priority else None,
                "issuetype": i.fields.issuetype.name,
            }
            for i in issues
        ],
    }


def build_payload(raw: dict) -> dict:
    by_epic: dict[str, list] = defaultdict(list)
    for issue in raw["issues"]:
        if issue.get("parent"):
            by_epic[issue["parent"]].append(issue)

    epics_out = []
    for epic in raw["epics"]:
        kids = by_epic.get(epic["key"], [])
        done = sum(1 for k in kids if is_done(k["status"]))
        ip = sum(1 for k in kids if is_ip(k["status"]))
        todo = len(kids) - done - ip
        total = len(kids)
        a_map: dict[str, dict] = defaultdict(lambda: {"done": 0, "ip": 0, "todo": 0, "total": 0})
        for k in kids:
            name = k["assignee"] or "Unassigned"
            a_map[name]["total"] += 1
            if is_done(k["status"]):
                a_map[name]["done"] += 1
            elif is_ip(k["status"]):
                a_map[name]["ip"] += 1
            else:
                a_map[name]["todo"] += 1
        epics_out.append(
            {
                "key": epic["key"],
                "summary": epic["summary"],
                "status": epic["status"],
                "done": done,
                "ip": ip,
                "todo": todo,
                "total": total,
                "pct": round(100 * done / total) if total else 0,
                "pct_w": round(100 * (done + 0.5 * ip) / total) if total else 0,
                "assignees": [
                    {"name": n, **s}
                    for n, s in sorted(a_map.items(), key=lambda x: -x[1]["total"])
                ],
            }
        )
    epics_out.sort(key=lambda x: (x["total"] == 0, -x["pct_w"], x["summary"]))

    assignees: dict[str, dict] = defaultdict(
        lambda: {"done": 0, "ip": 0, "todo": 0, "total": 0, "epics": set()}
    )
    for issue in raw["issues"]:
        name = issue["assignee"] or "Unassigned"
        assignees[name]["total"] += 1
        if is_done(issue["status"]):
            assignees[name]["done"] += 1
        elif is_ip(issue["status"]):
            assignees[name]["ip"] += 1
        else:
            assignees[name]["todo"] += 1
        if issue.get("parent"):
            assignees[name]["epics"].add(issue["parent"])

    assignees_out = []
    for name, s in sorted(
        assignees.items(), key=lambda x: (-x[1]["done"], -x[1]["ip"], -x[1]["total"])
    ):
        total = s["total"]
        assignees_out.append(
            {
                "name": name,
                "done": s["done"],
                "ip": s["ip"],
                "todo": s["todo"],
                "total": total,
                "pct": round(100 * s["done"] / total) if total else 0,
                "pct_w": round(100 * (s["done"] + 0.5 * s["ip"]) / total) if total else 0,
                "epic_count": len(s["epics"]),
            }
        )

    tot = len(raw["issues"])
    tot_done = sum(1 for i in raw["issues"] if is_done(i["status"]))
    tot_ip = sum(1 for i in raw["issues"] if is_ip(i["status"]))
    tot_todo = tot - tot_done - tot_ip

    if ZoneInfo:
        generated = datetime.datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%Y-%m-%d %H:%M")
    else:
        generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    return {
        "site": raw["site"],
        "generated": generated,
        "overall": {
            "total": tot,
            "done": tot_done,
            "ip": tot_ip,
            "todo": tot_todo,
            "pct": round(100 * tot_done / tot) if tot else 0,
            "pct_w": round(100 * (tot_done + 0.5 * tot_ip) / tot) if tot else 0,
            "epics": len(raw["epics"]),
            "epics_with_work": sum(1 for e in epics_out if e["total"] > 0),
        },
        "epics": epics_out,
        "assignees": assignees_out,
    }


def render(payload: dict, template: str) -> str:
    # Keep JSON safe inside <script type="application/json">
    blob = json.dumps(payload, ensure_ascii=False, indent=2)
    blob = blob.replace("<", "\\u003c")
    if "__DATA__" not in template:
        raise SystemExit("dashboard template missing __DATA__ placeholder")
    return template.replace("__DATA__", blob)


def main() -> None:
    dash = Path(__file__).resolve().parent
    template_path = dash / "index.template.html"
    out_path = dash / "index.html"
    data_path = dash / "data.json"

    # Prefer template; fall back to current index if regenerating from itself
    if template_path.is_file():
        template = template_path.read_text()
    else:
        current = out_path.read_text()
        # Strip previously injected JSON back to placeholder
        start = current.find('<script id="dashboard-data"')
        end = current.find("</script>", start)
        if start == -1 or end == -1:
            raise SystemExit("Cannot find dashboard-data script in index.html")
        # include through closing script tag end
        end = end + len("</script>")
        before = current[:start]
        after = current[end:]
        template = (
            before
            + '<script id="dashboard-data" type="application/json">\n__DATA__\n  </script>'
            + after
        )
        template_path.write_text(template)

    print("Fetching Jira…", flush=True)
    # Auth stays in local .env / process env via require_env — never hardcoded.
    raw = fetch()
    payload = build_payload(raw)
    html = render(payload, template_path.read_text())
    data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    out_path.write_text(html)

    # Publish copy for GitHub Pages (branch main, /docs).
    docs_dir = ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    (docs_dir / ".nojekyll").write_text("")
    (docs_dir / "index.html").write_text(html)
    (docs_dir / "data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    print(f"Wrote {out_path.relative_to(ROOT)}")
    print(f"Wrote {(docs_dir / 'index.html').relative_to(ROOT)} (GitHub Pages)")
    print(
        f"Overall {payload['overall']['pct']}% done "
        f"({payload['overall']['done']}/{payload['overall']['total']}) · "
        f"{len(payload['epics'])} epics · {len(payload['assignees'])} assignees"
    )


if __name__ == "__main__":
    main()
