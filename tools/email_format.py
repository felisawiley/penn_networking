"""Convert briefing Markdown into Gmail-safe HTML.

The GitHub archive stays Markdown. Gmail does not render Markdown, so the
send path wraps the same text in inline-styled HTML before calling
GMAIL_SEND_EMAIL with is_html=True.
"""

from __future__ import annotations

import html
import re

_HEADING = re.compile(r"^(#{1,3})\s+(.*)$")
_ORDERED = re.compile(r"^(\d+)\.\s+(.*)$")
_BULLET = re.compile(r"^([-*])\s+(.*)$")
_HR = re.compile(r"^-{3,}\s*$")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+)`")
_NAME_SPLIT = re.compile(r"\s+[—–-]\s+")


WRAPPER_STYLE = (
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;"
    "font-size:16px;line-height:1.55;color:#1a1a1a;"
)
H1_STYLE = "font-size:22px;line-height:1.3;font-weight:700;color:#111;margin:0 0 10px;"
H2_STYLE = (
    "font-size:13px;line-height:1.4;font-weight:700;letter-spacing:0.06em;"
    "text-transform:uppercase;color:#4b5563;border-bottom:1px solid #e5e7eb;"
    "padding:0 0 6px;margin:28px 0 12px;"
)
H3_STYLE = "font-size:16px;line-height:1.4;font-weight:700;color:#111;margin:20px 0 8px;"
P_STYLE = "margin:0 0 12px;color:#1f2937;"
LI_STYLE = "margin:0 0 18px;padding:0;"
OL_STYLE = "margin:0;padding-left:1.3em;"
UL_STYLE = "margin:0 0 12px;padding-left:1.3em;"
HR_STYLE = "border:none;border-top:1px solid #e5e7eb;margin:24px 0;"
DRAFT_BOX_STYLE = (
    "margin:8px 0 0;padding:10px 14px;background:#f3f6fb;"
    "border-left:3px solid #163a70;color:#111;"
)
DRAFT_LABEL_STYLE = (
    "font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
    "color:#163a70;font-weight:700;margin:0 0 4px;"
)
A_STYLE = "color:#163a70;"


def markdown_to_email_html(markdown: str) -> str:
    """Return a full HTML document suitable for GMAIL_SEND_EMAIL(is_html=True)."""
    inner = _blocks_to_html(markdown.replace("\r\n", "\n").replace("\r", "\n"))
    return (
        "<!DOCTYPE html><html><body style=\"margin:0;padding:0;background:#ffffff;\">"
        f'<div style="{WRAPPER_STYLE}max-width:640px;margin:0 auto;padding:8px 4px 24px;">'
        f"{inner}"
        "</div></body></html>"
    )


def _inline(text: str) -> str:
    """Escape, then apply a tiny Markdown inline subset (links, bold, code)."""
    placeholders: list[str] = []

    def _stash_link(match: re.Match[str]) -> str:
        label = html.escape(match.group(1))
        href = html.escape(match.group(2), quote=True)
        placeholders.append(f'<a href="{href}" style="{A_STYLE}">{label}</a>')
        return f"\x00L{len(placeholders) - 1}\x00"

    text = _LINK.sub(_stash_link, text)
    text = html.escape(text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _CODE.sub(r"<code>\1</code>", text)
    for i, replacement in enumerate(placeholders):
        text = text.replace(f"\x00L{i}\x00", replacement)
    return text


def _heading_html(level: int, title: str) -> str:
    style = {1: H1_STYLE, 2: H2_STYLE, 3: H3_STYLE}[level]
    tag = f"h{level}"
    return f'<{tag} style="{style}">{_inline(title)}</{tag}>'


def _emphasize_name(item: str) -> str:
    """Bold the person name when the item is 'Name — rest'."""
    parts = _NAME_SPLIT.split(item, maxsplit=1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        return _inline(item)
    return f"<strong>{_inline(parts[0].strip())}</strong> — {_inline(parts[1].strip())}"


def _draft_html(text: str) -> str:
    body = text.strip()
    lower = body.lower()
    if lower.startswith("draft:"):
        body = body[6:].strip()
    if (body.startswith('"') and body.endswith('"')) or (
        body.startswith("\u201c") and body.endswith("\u201d")
    ):
        body = body[1:-1].strip()
    return (
        f'<div style="{DRAFT_BOX_STYLE}">'
        f'<div style="{DRAFT_LABEL_STYLE}">Draft</div>'
        f"<div>{_inline(body)}</div>"
        "</div>"
    )


def _is_indented_continuation(line: str) -> bool:
    if not line.strip():
        return False
    if line.startswith(" ") or line.startswith("\t"):
        return True
    return line.lstrip().lower().startswith("draft:")


def _collect_list(
    lines: list[str], start: int, pattern: re.Pattern[str]
) -> tuple[list[tuple[str, list[str]]], int]:
    items: list[tuple[str, list[str]]] = []
    i = start
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            # Blank line inside a list: peek ahead. Another item continues the list.
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and pattern.match(lines[j]):
                i = j
                continue
            break
        match = pattern.match(raw)
        if match:
            items.append((match.group(2), []))
            i += 1
            continue
        if items and _is_indented_continuation(raw):
            items[-1][1].append(raw.strip())
            i += 1
            continue
        break
    return items, i


def _list_item_html(first: str, continuations: list[str]) -> str:
    parts = [_emphasize_name(first)]
    for cont in continuations:
        if cont.lower().startswith("draft:"):
            parts.append(_draft_html(cont))
        else:
            parts.append(f'<div style="margin-top:4px;">{_inline(cont)}</div>')
    return "".join(parts)


def _blocks_to_html(markdown: str) -> str:
    lines = markdown.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if _HR.match(line.strip()):
            out.append(f'<hr style="{HR_STYLE}">')
            i += 1
            continue
        heading = _HEADING.match(line)
        if heading:
            out.append(_heading_html(len(heading.group(1)), heading.group(2)))
            i += 1
            continue
        if _ORDERED.match(line):
            items, i = _collect_list(lines, i, _ORDERED)
            lis = "".join(
                f'<li style="{LI_STYLE}">{_list_item_html(first, conts)}</li>'
                for first, conts in items
            )
            out.append(f'<ol style="{OL_STYLE}">{lis}</ol>')
            continue
        if _BULLET.match(line):
            items, i = _collect_list(lines, i, _BULLET)
            lis = "".join(
                f'<li style="{LI_STYLE}">{_list_item_html(first, conts)}</li>'
                for first, conts in items
            )
            out.append(f'<ul style="{UL_STYLE}">{lis}</ul>')
            continue
        para: list[str] = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append(f'<p style="{P_STYLE}">{" ".join(_inline(p) for p in para)}</p>')
    return "".join(out) or f'<p style="{P_STYLE}"></p>'


def _is_block_start(line: str) -> bool:
    stripped = line.strip()
    return bool(
        _HEADING.match(stripped)
        or _ORDERED.match(stripped)
        or _BULLET.match(stripped)
        or _HR.match(stripped)
    )
