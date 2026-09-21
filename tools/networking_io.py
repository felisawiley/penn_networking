#!/usr/bin/env python3
"""MCP-independent I/O layer for the Weekly Networking automation.

Cursor Cloud Agent *automations* currently do not receive the MCP servers that
are attached in the dashboard/automation UI (the servers are absent from the
run's tool catalog, not merely unauthenticated). This module lets the automation
do all of its Google Sheets / Gmail / GitHub I/O through committed code that
authenticates with a single environment secret (``COMPOSIO_API_KEY``), which
*does* reach the automation VM, instead of depending on the broken MCP layer.

It talks to Composio's direct tool-execution API (the same backend the Composio
MCP proxies), so behavior matches what the automation used to do via
``@[MCP: composio]``.

Auth / configuration (set as Cursor secrets so they are injected as env vars):
  COMPOSIO_API_KEY   required  Composio API key (dashboard.composio.dev)
  COMPOSIO_USER_ID   required  Composio user/entity id that owns the Google +
                               Gmail connections (run ``self-check`` to verify)

Usage (the automation calls these via the shell):
  python tools/networking_io.py self-check
  python tools/networking_io.py read-sheet
  python tools/networking_io.py read-log
  python tools/networking_io.py exec --slug GMAIL_FETCH_EMAILS --args '{"query":"..."}'
  python tools/networking_io.py append-rows --tab outreach_log --rows-json '[[...]]' --commit
  python tools/networking_io.py send-briefing --date 2026-09-14 --body-file brief.md --commit

Every command prints JSON to stdout. Write/send commands are DRY-RUN unless
``--commit`` is passed, so the automation can preview before mutating anything.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# The tracker is the source of truth. These identifiers were confirmed live.
SPREADSHEET_ID = "1fNhbKbk5Y19RMOR2rr760Uw483mHPG3wVtan6mVosrg"
MAIN_TAB = "'26"            # literal tab name (leading apostrophe is real)
LOG_TAB = "outreach_log"
BRIEFING_TO = "felisawiley@gmail.com"


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


def a1_tab(tab: str) -> str:
    """Quote a sheet/tab name for A1 notation (double internal single quotes)."""
    return "'" + tab.replace("'", "''") + "'"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"{name} is not set. Add it as a Cursor secret so it is injected "
            f"into the automation VM as an environment variable."
        )
    return value


def get_client():
    """Return a configured Composio client (imported lazily)."""
    api_key = _require_env("COMPOSIO_API_KEY")
    try:
        from composio import Composio  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ConfigError(
            "The 'composio' package is not installed. Add it to requirements.txt "
            "and ensure the environment install step runs 'pip install -r requirements.txt'."
        ) from exc
    return Composio(api_key=api_key)


def _normalize(result: Any) -> dict[str, Any]:
    """Normalize an SDK response object (or dict) to a plain dict."""
    if isinstance(result, dict):
        return result
    for attr in ("model_dump", "dict", "to_dict"):
        method = getattr(result, attr, None)
        if callable(method):
            return method()
    return {"data": getattr(result, "data", result), "successful": getattr(result, "successful", True)}


def execute(
    slug: str,
    arguments: dict[str, Any],
    *,
    client=None,
    user_id: str | None = None,
    connected_account_id: str | None = None,
) -> dict[str, Any]:
    """Execute a single Composio tool. Auth by connected_account_id or user_id.

    connected_account_id (or the per-toolkit *_ACCOUNT_ID env vars) targets one
    exact account and needs no user id. Otherwise a user id is required (arg or
    COMPOSIO_USER_ID). Run ``list-connections`` to discover either value.
    """
    client = client or get_client()
    kwargs: dict[str, Any] = {"arguments": arguments, "dangerously_skip_version_check": True}
    if connected_account_id:
        kwargs["connected_account_id"] = connected_account_id
    else:
        uid = user_id or os.environ.get("COMPOSIO_USER_ID")
        if not uid:
            raise ConfigError(
                "Set COMPOSIO_USER_ID (or a per-toolkit *_ACCOUNT_ID). "
                "Run 'python tools/networking_io.py list-connections' to find it."
            )
        kwargs["user_id"] = uid
    return _normalize(client.tools.execute(slug, **kwargs))


def list_connections(client=None) -> dict[str, Any]:
    """List Composio connected accounts (to discover user_id / account ids)."""
    client = client or get_client()
    return _normalize(client.connected_accounts.list())


# --- Sheet helpers ---------------------------------------------------------

def _sheets_account() -> str | None:
    return os.environ.get("COMPOSIO_SHEETS_ACCOUNT_ID")


def _gmail_account() -> str | None:
    return os.environ.get("COMPOSIO_GMAIL_ACCOUNT_ID")


def read_sheet(client=None, user_id: str | None = None) -> dict[str, Any]:
    return execute(
        "GOOGLESHEETS_BATCH_GET",
        {"spreadsheet_id": SPREADSHEET_ID, "ranges": [f"{a1_tab(MAIN_TAB)}!A1:I1000"]},
        client=client,
        user_id=user_id,
        connected_account_id=_sheets_account(),
    )


def read_log(client=None, user_id: str | None = None) -> dict[str, Any]:
    return execute(
        "GOOGLESHEETS_BATCH_GET",
        {"spreadsheet_id": SPREADSHEET_ID, "ranges": [f"{a1_tab(LOG_TAB)}!A1:H1000"]},
        client=client,
        user_id=user_id,
        connected_account_id=_sheets_account(),
    )


def append_rows(tab: str, rows: list[list[Any]], client=None, user_id: str | None = None) -> dict[str, Any]:
    return execute(
        "GOOGLESHEETS_BATCH_UPDATE",
        {
            "spreadsheet_id": SPREADSHEET_ID,
            "sheet_name": tab,
            "values": rows,
            "includeValuesInResponse": True,
        },
        client=client,
        user_id=user_id,
        connected_account_id=_sheets_account(),
    )


def send_briefing(subject: str, body: str, client=None, user_id: str | None = None) -> dict[str, Any]:
    return execute(
        "GMAIL_SEND_EMAIL",
        {"recipient_email": BRIEFING_TO, "subject": subject, "body": body},
        client=client,
        user_id=user_id,
        connected_account_id=_gmail_account(),
    )


# --- CLI -------------------------------------------------------------------

def _print(obj: Any) -> None:
    json.dump(obj, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def cmd_self_check(args) -> int:
    report: dict[str, Any] = {"checks": []}
    api_present = bool(os.environ.get("COMPOSIO_API_KEY"))
    identity_present = bool(
        args.user_id
        or os.environ.get("COMPOSIO_USER_ID")
        or _sheets_account()
        or _gmail_account()
    )
    report["checks"].append({"env": "COMPOSIO_API_KEY", "present": api_present})
    report["checks"].append({"env": "COMPOSIO_USER_ID (or *_ACCOUNT_ID)", "present": identity_present})
    if not api_present:
        report["ok"] = False
        report["hint"] = (
            "COMPOSIO_API_KEY is not in this process environment. "
            "Authorizing or reconnecting Composio/Gmail MCP does not set it: "
            "HTTP MCP credentials stay on Cursor's proxy and never enter the VM, "
            "and this automation's tool catalog does not include Composio. "
            "Add a Cloud Agent environment secret named exactly COMPOSIO_API_KEY "
            "(Composio project API key, not the ck_ consumer key), plus "
            "COMPOSIO_USER_ID, on this environment — then start a new run "
            "(secrets do not hot-reload into an already-running VM)."
        )
        _print(report)
        return 1

    # Stage 1: project-key check that needs no connected account (per Composio's
    # unattended-agent guide). Isolates "bad/absent project key" from "app not
    # connected". A placeholder user_id is fine; this tool needs no account.
    try:
        resp = execute("HACKERNEWS_GET_USER", {"username": "pg"}, user_id=args.user_id or "self-check")
        report["project_key_ok"] = bool(resp.get("successful", True))
    except Exception as exc:  # noqa: BLE001 - surface any failure to the caller
        report["project_key_ok"] = False
        report["project_key_error"] = str(exc)
        report["ok"] = False
        _print(report)
        return 1

    if not identity_present:
        report["ok"] = False
        report["connected_account_ok"] = None
        report["hint"] = "Project key works. Run 'list-connections' to find your user_id, then set COMPOSIO_USER_ID."
        _print(report)
        return 1

    # Stage 2: connected-account check against the real tracker.
    try:
        resp = execute(
            "GOOGLESHEETS_GET_SHEET_NAMES",
            {"spreadsheet_id": SPREADSHEET_ID},
            user_id=args.user_id,
            connected_account_id=_sheets_account(),
        )
        report["sheet_access"] = resp.get("data", resp)
        report["connected_account_ok"] = bool(resp.get("successful", True))
    except Exception as exc:  # noqa: BLE001 - surface any failure to the caller
        report["connected_account_ok"] = False
        report["connected_account_error"] = str(exc)

    report["ok"] = bool(report.get("project_key_ok") and report.get("connected_account_ok"))
    _print(report)
    return 0 if report["ok"] else 1


def cmd_list_connections(args) -> int:
    _print(list_connections())
    return 0


def cmd_read_sheet(args) -> int:
    _print(read_sheet(user_id=args.user_id))
    return 0


def cmd_read_log(args) -> int:
    _print(read_log(user_id=args.user_id))
    return 0


def cmd_exec(args) -> int:
    arguments = json.loads(args.args) if args.args else {}
    _print(execute(args.slug, arguments, user_id=args.user_id))
    return 0


def cmd_append_rows(args) -> int:
    rows = json.loads(args.rows_json)
    if not args.commit:
        _print({"dry_run": True, "would_append_to": args.tab, "rows": rows})
        return 0
    _print(append_rows(args.tab, rows, user_id=args.user_id))
    return 0


def cmd_send_briefing(args) -> int:
    body = sys.stdin.read() if args.body_file == "-" else open(args.body_file, encoding="utf-8").read()
    subject = f"Weekly Networking \u2013 {args.date}"
    if not args.commit:
        _print({"dry_run": True, "to": BRIEFING_TO, "subject": subject, "body_preview": body[:500]})
        return 0
    _print(send_briefing(subject, body, user_id=args.user_id))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", default=os.environ.get("COMPOSIO_USER_ID"),
                        help="Composio user/entity id (default: $COMPOSIO_USER_ID)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("self-check", help="Verify secrets and live sheet access").set_defaults(func=cmd_self_check)
    sub.add_parser("list-connections", help="List Composio connected accounts (find user_id / account ids)").set_defaults(func=cmd_list_connections)
    sub.add_parser("read-sheet", help="Read the main tracker tab").set_defaults(func=cmd_read_sheet)
    sub.add_parser("read-log", help="Read the outreach_log tab").set_defaults(func=cmd_read_log)

    p_exec = sub.add_parser("exec", help="Execute any Composio tool by slug")
    p_exec.add_argument("--slug", required=True)
    p_exec.add_argument("--args", default="{}", help="JSON object of arguments")
    p_exec.set_defaults(func=cmd_exec)

    p_append = sub.add_parser("append-rows", help="Append rows to a tab (dry-run unless --commit)")
    p_append.add_argument("--tab", required=True)
    p_append.add_argument("--rows-json", required=True, help="JSON array of row arrays")
    p_append.add_argument("--commit", action="store_true")
    p_append.set_defaults(func=cmd_append_rows)

    p_send = sub.add_parser("send-briefing", help="Email the briefing to Fee (dry-run unless --commit)")
    p_send.add_argument("--date", required=True, help="Briefing date YYYY-MM-DD")
    p_send.add_argument("--body-file", required=True, help="Path to body file, or '-' for stdin")
    p_send.add_argument("--commit", action="store_true")
    p_send.set_defaults(func=cmd_send_briefing)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        _print({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
