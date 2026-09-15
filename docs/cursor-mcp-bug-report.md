# Bug report: MCP servers not attached to Cloud Agent automation runs

Ready to file with Cursor support / forum. All evidence was gathered from the
account's own runs.

## Summary

MCP servers that are attached in the automation's settings do not appear in the
scheduled Cloud Agent automation run's tool catalog. The servers are **absent**
(nothing to authenticate), not merely unauthenticated. The same servers work
correctly in interactive Cloud Agent runs for the same user and repo.

## Environment

- Automation: `Weekly Networking`, id `6c2c5ce8-b058-11f1-bf4b-42ffb4d10ea7`
- Owner: felisawiley@gmail.com (user id 120872061)
- Repo: `github.com/felisawiley/penn_networking`
- Automation model: `cursor-grok-4.6-high-fast`

## Affected runs (source: automations)

- `bc-ce186ac4-8bb6-40d5-85f4-b4e6416b4a14`
- `bc-962d9aa4-7b40-48f7-b6de-25f011eeece5`
- `bc-1c333cd7-bfa0-4668-99ae-7cb5ae7f5432`
- `bc-79c0b603-fb65-4d00-aa3c-af03dd06ca3a`
- `bc-46baaa51-8b02-40b2-8a51-ae9e13a0aa68`

## Evidence

From the affected runs' transcripts, the run's tool catalog contained only
`Cursor Automation Tools` (single tool `open_git_pr`), `cursor`, `cursor-cloud`,
and `cursor-subscriptions`. Direct namespace lookups returned:

- `namespace "composio" not found`
- `namespace "gmail" not found`
- `namespace "google-drive" not found`
- `namespace "github" not found`

Authentication attempts returned:

- `Interactive MCP authentication is only available in the Cursor desktop IDE`

Other observations:

- **Zero** `mcp_auth_error` events were recorded on any affected run.
- Egress was unrestricted (`restricted: false`) on all runs.

## Contrast (works here)

In an interactive Cloud Agent run for the same user/repo
(`bc-1d4558fb-f19d-4afa-8d34-b73113b8f8bf`, source `setup`), the namespaces
`Composio`, `Gmail`, `Github`, and `Google-drive` were all `ready`, and live
read‑only calls succeeded (Google Sheets read of the tracker, Gmail label list,
GitHub identity). Only the `automations`-source runs lacked the servers.

## Steps already taken by the user

- Disconnected and reconnected the MCP tools multiple times (3×).
- Deleted and re‑added them within the automation section (3×).
- Result unchanged: the servers still do not appear in the automation run.

## Impact

The automation cannot read/write the source‑of‑truth Google Sheet or send the
weekly email, so every run fails closed.

## Requests

1. Confirm whether MCP servers enabled in an automation's settings are expected
   to be present in the scheduled run's tool catalog.
2. Trace why these servers are absent for `automations`-source runs while present
   for interactive runs of the same user/repo.
3. Clarify the supported, reliable configuration path for MCP in automations
   (and whether `.cursor/mcp.json` is honored).
