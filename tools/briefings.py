#!/usr/bin/env python3
"""Developer CLI for the Penn networking weekly briefing archive.

This is a zero-dependency tool (Python standard library only) for working
with the Markdown briefing files under `briefings/`.

Subcommands:
  validate   Check that every briefing file is well-formed.
  new        Scaffold a new weekly (Monday) briefing from a template.
  index      Print (or write) an index of all briefings.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIEFINGS_DIR = REPO_ROOT / "briefings"
FILENAME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.md$")


def briefing_files(directory: Path) -> list[Path]:
    """Return sorted briefing files (excludes README and other docs)."""
    return sorted(p for p in directory.glob("*.md") if FILENAME_RE.match(p.name))


def parse_date_from_name(name: str) -> dt.date | None:
    match = FILENAME_RE.match(name)
    if not match:
        return None
    try:
        return dt.date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None


def validate(directory: Path) -> int:
    """Validate every briefing file. Returns process exit code."""
    files = briefing_files(directory)
    if not files:
        print(f"No briefing files found in {directory}", file=sys.stderr)
        return 1

    errors: list[str] = []
    for path in files:
        name = path.name
        date = parse_date_from_name(name)
        if date is None:
            errors.append(f"{name}: filename is not a valid YYYY-MM-DD.md date")
            continue
        if date.weekday() != 0:  # Monday == 0
            errors.append(f"{name}: date {date} is a {date.strftime('%A')}, not a Monday")

        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"{name}: file is empty")
            continue
        first_line = text.lstrip().splitlines()[0]
        if not first_line.startswith("# "):
            errors.append(f"{name}: missing top-level '# ' heading on first line")

    for err in errors:
        print(f"ERROR: {err}", file=sys.stderr)

    print(f"Checked {len(files)} briefing file(s); {len(errors)} error(s).")
    return 1 if errors else 0


TEMPLATE = """# Weekly Networking – {date}

**Status: DRAFT — fill in before publishing.**

## Slots

### Last week, still open

To be filled in before publishing.

### New five

To be filled in before publishing.

### Dedicated follow-up slot

To be filled in before publishing.

### Drafts

To be filled in before publishing.

---

Sent check: _TBD_.
Sheet writes: _TBD_.
"""


def most_recent_monday(today: dt.date) -> dt.date:
    return today - dt.timedelta(days=today.weekday())


def new_briefing(directory: Path, date_str: str | None, force: bool) -> int:
    if date_str:
        try:
            date = dt.date.fromisoformat(date_str)
        except ValueError:
            print(f"Invalid date '{date_str}'; expected YYYY-MM-DD", file=sys.stderr)
            return 1
    else:
        date = most_recent_monday(dt.date.today())

    if date.weekday() != 0:
        print(f"Warning: {date} is a {date.strftime('%A')}, not a Monday.", file=sys.stderr)

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{date.isoformat()}.md"
    if target.exists() and not force:
        print(f"Refusing to overwrite existing {target} (use --force)", file=sys.stderr)
        return 1

    target.write_text(TEMPLATE.format(date=date.isoformat()), encoding="utf-8")
    print(f"Created {target}")
    return 0


def build_index(directory: Path) -> str:
    files = briefing_files(directory)
    lines = ["# Briefing index", "", f"{len(files)} briefing(s).", ""]
    for path in reversed(files):  # newest first
        date = parse_date_from_name(path.name)
        lines.append(f"- [{date.isoformat()}]({path.name})")
    return "\n".join(lines) + "\n"


def index(directory: Path, output: str | None) -> int:
    content = build_index(directory)
    if output:
        Path(output).write_text(content, encoding="utf-8")
        print(f"Wrote index to {output}")
    else:
        sys.stdout.write(content)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        default=str(BRIEFINGS_DIR),
        help="Briefings directory (default: %(default)s)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="Validate all briefing files")

    p_new = sub.add_parser("new", help="Scaffold a new weekly briefing")
    p_new.add_argument("date", nargs="?", help="Monday date YYYY-MM-DD (default: this week)")
    p_new.add_argument("--force", action="store_true", help="Overwrite if the file exists")

    p_index = sub.add_parser("index", help="Print or write a briefing index")
    p_index.add_argument("-o", "--output", help="Write index to this file instead of stdout")

    args = parser.parse_args(argv)
    directory = Path(args.dir)

    if args.command == "validate":
        return validate(directory)
    if args.command == "new":
        return new_briefing(directory, args.date, args.force)
    if args.command == "index":
        return index(directory, args.output)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
