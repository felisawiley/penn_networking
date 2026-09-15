# Weekly Networking automation

This document defines the Weekly Networking automation and — importantly — makes
it independent of Cursor's MCP layer, which does not reliably reach Cloud Agent
automation runs.

## Why this exists (the bug)

The scheduled automation kept failing "fail closed" because the third‑party MCP
servers (Composio / Gmail / Google Sheets / Google Drive / GitHub) were **absent
from the automation run's tool catalog** — not merely unauthenticated. Evidence
from the automation's own run transcripts:

- `namespace "composio" not found` (and the same for `gmail`, `google-drive`,
  `github`); the only action tool present was `open_git_pr`.
- `Interactive MCP authentication is only available in the Cursor desktop IDE`.
- **Zero** MCP auth‑error events were recorded for the runs.

Reconnecting / deleting / re‑adding the servers in the automation UI does not fix
this, and `.cursor/mcp.json` is not reliably honored for automations (Cursor has
stated the supported path is dashboard config, and config interpolation is broken
for cloud‑agent MCP). See `docs/cursor-mcp-bug-report.md`.

## The fix: run I/O through committed code + one secret

Environment secrets *are* injected into automation VMs as environment variables,
even though MCP servers are not. So the automation performs all Google Sheets /
Gmail I/O through `tools/networking_io.py`, which authenticates with a single
Composio **project** API key and executes tools directly (Composio's documented
unattended‑agent path). No MCP attachment required.

This matches Composio's own guidance for automations:
<https://docs.composio.dev/docs/agent-setup/unattended-authentication>. The
programmatic path uses a project key (`COMPOSIO_API_KEY` / REST `x-api-key`
against `POST /api/v3.1/tools/execute/{slug}`) plus the `user_id` that owns the
Google connections. Two gotchas the docs call out:

- The `ck_...` consumer key + `x-consumer-api-key` header is only for interactive
  MCP clients (Claude Desktop, Cursor, etc.), **not** scripts. Scripts use the
  project key.
- `composio login --agent` creates a *separate* agent account that cannot access
  your Gmail/Sheets. Use **your** project key and user id, not an agent account.

The Composio agent skill is installed in the repo at `.agents/skills/composio/`
(via `npx skills add ComposioHQ/composio --skill composio`) as guidance; note a
skill is documentation only and does **not** by itself give a scheduled run
runtime access to Composio — that is what the key + this script provide.

### One‑time setup (the only hands‑on step)

Add these as Cursor secrets (personal or repo scope) so they are injected into
the automation VM:

| Secret | Where to get it |
| --- | --- |
| `COMPOSIO_API_KEY` | dashboard.composio.dev → the project that owns your Gmail/Sheets connections → API key |
| `COMPOSIO_USER_ID` | the Composio user id that owns those connections |

Then verify from any run:

```bash
python tools/networking_io.py self-check
```

A healthy result returns `"ok": true`, with `project_key_ok` (key valid) and
`connected_account_ok` (Google connection reachable) both true plus the tracker's
sheet names.

## Automation prompt (MCP‑free)

Use this as the automation's instructions. It is the original logic with every
`@[MCP: ...]` call replaced by a `tools/networking_io.py` command.

> You are Fee Wiley's weekly networking agent (feewiley.co,
> linkedin.com/in/felisawiley). Fee is MCIT at Penn Engineering (grad Summer
> 2027), works on clinical NLP / ACAM at Penn Medicine AI‑4‑AI, connected to
> Silver Creek Insights and Architect of Calm. Prefer people who fit that mix.
>
> Run in America/New_York. One Monday briefing only. Do not email guests. Do not
> set Status to yes. Never send outreach on Fee's behalf.
>
> Do all I/O through the committed script (no MCP):
>
> - Read tracker: `python tools/networking_io.py read-sheet`
> - Read log: `python tools/networking_io.py read-log`
> - Search Penn mail (last 7 days, `deliveredto:`/`to:` fwiley1@engineering.upenn.edu
>   and fwiley1@seas.upenn.edu; fall back to label `Penn Networking`):
>   `python tools/networking_io.py exec --slug GMAIL_FETCH_EMAILS --args '{"query":"..."}'`
> - Append new guest rows / outreach_log rows / write receive_date &
>   last_featured_reason: `python tools/networking_io.py append-rows --tab '26' --rows-json '[...]' --commit`
>   (omit `--commit` first to preview).
> - Email Fee the briefing: `python tools/networking_io.py send-briefing --date YYYY-MM-DD --body-file brief.md --commit`.
>
> SOURCE OF TRUTH: the Google Sheet (`1fNhbKbk5Y19RMOR2rr760Uw483mHPG3wVtan6mVosrg`,
> main tab `'26`, log tab `outreach_log`). Columns on the main tab: Date, Name,
> Role / Affiliation, Penn Connection, Recent Accomplishment, Status
> (blank / yes / skip), receive_date, email_date, last_featured_reason.
> outreach_log columns: week_of, name, selection_reason, suggested_channel,
> email_type, receive_date, notes, status_at_feature.
>
> FAIL CLOSED: if `read-sheet` fails, stop and email only an error to
> felisawiley@gmail.com. Do not shuffle from memory.
>
> Then apply the original selection rules (status/eligibility, 6‑month cooldown,
> 3× repeat cap counted from outreach_log new‑five rows, rotation preferring
> never‑featured then oldest receive_date, forced‑mix new five, last‑week‑still‑open
> check‑in, dedicated follow‑up slot for email_date 14–21 days ago with Status yes),
> write the briefing to `briefings/YYYY-MM-DD.md`, open a PR titled
> `Weekly Networking – YYYY-MM-DD` into `main`, merge it, and open a matching issue.

The full original rule text is preserved verbatim in
`docs/weekly-networking-rules.md`.

## Verifying end to end

```bash
python tools/networking_io.py self-check        # secrets + live sheet read
python tools/networking_io.py read-sheet         # current tracker rows (JSON)
python -m pytest tests/ -q                        # logic + CLI unit tests
```
