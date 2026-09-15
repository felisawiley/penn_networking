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
