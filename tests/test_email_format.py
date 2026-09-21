"""Tests for Markdown → Gmail HTML conversion."""

from __future__ import annotations

from pathlib import Path

from tools.email_format import markdown_to_email_html

REPO = Path(__file__).resolve().parent.parent


def test_headings_are_html_not_hashes():
    html = markdown_to_email_html("# Weekly Networking – 2026-09-14\n\n## New five\n\nHello")
    assert "##" not in html
    assert "<h1" in html
    assert "Weekly Networking" in html
    assert "<h2" in html
    assert "New five" in html


def test_numbered_person_and_draft_box():
    md = (
        "1. Danielle Mowery — CRIO, Penn Medicine · channel: coffee (Penn)\n"
        '   Draft: "Hi Dr. Mowery — coffee this week?"\n'
    )
    html = markdown_to_email_html(md)
    assert "<ol" in html
    assert "<strong>Danielle Mowery</strong>" in html
    assert "Draft" in html
    assert "Hi Dr. Mowery" in html
    assert "Draft:" not in html
    assert 'style=' in html


def test_escapes_html_and_keeps_links_and_bold():
    html = markdown_to_email_html(
        "See **status** and [the archive](https://github.com/felisawiley/penn_networking)."
        "\n\n<script>alert(1)</script>"
    )
    assert "<strong>status</strong>" in html
    assert 'href="https://github.com/felisawiley/penn_networking"' in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_real_briefing_has_no_raw_markdown_headings():
    md = (REPO / "briefings" / "2026-09-14.md").read_text(encoding="utf-8")
    html = markdown_to_email_html(md)
    assert "## Last week" not in html
    assert "## New five" not in html
    assert "<h2" in html
    assert "Danielle Mowery" in html
    assert "Neil Sehgal" in html
    assert "Dedicated follow-up" in html
