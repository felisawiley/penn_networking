"""Unit tests for tools/networking_io.py (no network; fake Composio client)."""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import networking_io as nio  # noqa: E402


class FakeTools:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def execute(self, slug, arguments, user_id, dangerously_skip_version_check):
        self.calls.append(
            {
                "slug": slug,
                "arguments": arguments,
                "user_id": user_id,
                "skip_version": dangerously_skip_version_check,
            }
        )
        return self._response


class FakeClient:
    def __init__(self, response):
        self.tools = FakeTools(response)


def test_a1_tab_quotes_leading_apostrophe():
    assert nio.a1_tab("'26") == "'''26'"
    assert nio.a1_tab("outreach_log") == "'outreach_log'"


def test_execute_passes_expected_params_and_normalizes_dict():
    client = FakeClient({"successful": True, "data": {"ok": 1}})
    out = nio.execute("SLUG", {"a": 1}, client=client, user_id="u1")
    assert out == {"successful": True, "data": {"ok": 1}}
    call = client.tools.calls[0]
    assert call["slug"] == "SLUG"
    assert call["arguments"] == {"a": 1}
    assert call["user_id"] == "u1"
    assert call["skip_version"] is True


def test_execute_normalizes_object_with_model_dump():
    class Resp:
        def model_dump(self):
            return {"successful": True, "data": [1, 2, 3]}

    client = FakeClient(Resp())
    out = nio.execute("SLUG", {}, client=client, user_id="u1")
    assert out == {"successful": True, "data": [1, 2, 3]}


def test_read_sheet_builds_quoted_bounded_range():
    client = FakeClient({"successful": True, "data": {}})
    nio.read_sheet(client=client, user_id="u1")
    args = client.tools.calls[0]["arguments"]
    assert args["spreadsheet_id"] == nio.SPREADSHEET_ID
    assert args["ranges"] == ["'''26'!A1:I1000"]


def test_require_env_raises_configerror(monkeypatch):
    monkeypatch.delenv("COMPOSIO_API_KEY", raising=False)
    with pytest.raises(nio.ConfigError):
        nio._require_env("COMPOSIO_API_KEY")


def _run(argv, capsys):
    rc = nio.main(argv)
    out = capsys.readouterr().out
    return rc, (json.loads(out) if out.strip() else None)


def test_append_rows_dry_run_writes_nothing(capsys):
    rc, payload = _run(
        ["--user-id", "u1", "append-rows", "--tab", "outreach_log", "--rows-json", "[[\"a\",\"b\"]]"],
        capsys,
    )
    assert rc == 0
    assert payload["dry_run"] is True
    assert payload["would_append_to"] == "outreach_log"
    assert payload["rows"] == [["a", "b"]]


def test_send_briefing_dry_run(tmp_path, capsys):
    body = tmp_path / "brief.md"
    body.write_text("# Weekly Networking\n\nbody", encoding="utf-8")
    rc, payload = _run(
        ["--user-id", "u1", "send-briefing", "--date", "2026-09-14", "--body-file", str(body)],
        capsys,
    )
    assert rc == 0
    assert payload["dry_run"] is True
    assert payload["to"] == nio.BRIEFING_TO
    assert payload["subject"] == "Weekly Networking \u2013 2026-09-14"


def test_self_check_missing_secrets_returns_1(monkeypatch, capsys):
    monkeypatch.delenv("COMPOSIO_API_KEY", raising=False)
    monkeypatch.delenv("COMPOSIO_USER_ID", raising=False)
    rc, payload = _run(["self-check"], capsys)
    assert rc == 1
    assert payload["ok"] is False
    assert any(c["env"] == "COMPOSIO_API_KEY" and not c["present"] for c in payload["checks"])


def test_config_error_surfaced_as_rc2(monkeypatch, capsys):
    monkeypatch.delenv("COMPOSIO_API_KEY", raising=False)
    # read-sheet with no api key -> get_client raises ConfigError -> rc 2
    rc, payload = _run(["--user-id", "u1", "read-sheet"], capsys)
    assert rc == 2
    assert payload["ok"] is False
    assert "COMPOSIO_API_KEY" in payload["error"]
