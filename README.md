# Penn networking

Weekly Monday briefing archive for Penn guest-speaker outreach.

Each run writes `briefings/YYYY-MM-DD.md`, opens a pull request, and merges it into `main`. The Google Sheet remains the source of truth for Status, dates, and rotation.

Tracker: [Penn networking sheet](https://docs.google.com/spreadsheets/d/1fNhbKbk5Y19RMOR2rr760Uw483mHPG3wVtan6mVosrg/edit)

## Development

This repo is a Markdown archive. Two tools keep the briefings consistent:

- `tools/briefings.py` — a zero-dependency (Python 3 standard library) CLI.
- `markdownlint-cli2` — Markdown linting (installed via `npm install`).

### Setup

```bash
npm install
```

### Commands

```bash
npm run lint                 # lint all Markdown files
npm run validate             # check briefing filenames, dates, and headings
npm run new -- 2026-09-21    # scaffold briefings/2026-09-21.md (defaults to this Monday)
npm run index                # print a Markdown index of all briefings
```

The CLI can also be run directly, e.g. `python3 tools/briefings.py validate`.

### The weekly automation

The Monday briefing is produced by a Cursor automation. Because Cursor Cloud
Agent automations do not reliably receive MCP servers, the automation does its
Google Sheets / Gmail I/O through `tools/networking_io.py` using a single
`COMPOSIO_API_KEY` secret instead of MCP. See `AUTOMATION.md` for setup and the
MCP‑free prompt, `docs/weekly-networking-rules.md` for the original rules, and
`docs/cursor-mcp-bug-report.md` for the underlying Cursor bug.

```bash
pip install -r requirements.txt
python tools/networking_io.py self-check   # verify secrets + live sheet access
python -m pytest tests/ -q                  # run the test suite
```
