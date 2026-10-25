"""extract_text() のテスト

Claude Sonnet 5.5 以降では response.content の先頭が thinking ブロックになることが
あるため、``response.content[0].text`` ではなくこの関数を使う。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.clients.claude import extract_text
from src.config.settings import DEFAULT_CLAUDE_MODEL


def _response(*blocks):
    return SimpleNamespace(content=list(blocks))


class TestExtractText:
    def test_thinking_block_first_is_skipped(self):
        resp = _response(
            SimpleNamespace(type="thinking", thinking="...", signature="sig"),
            SimpleNamespace(type="text", text="かしこまりました。"),
        )
        assert extract_text(resp) == "かしこまりました。"

    def test_multiple_text_blocks_are_joined(self):
        resp = _response(
            SimpleNamespace(type="text", text="A"),
            SimpleNamespace(type="tool_use", id="x", name="t", input={}),
            SimpleNamespace(type="text", text="B"),
        )
        assert extract_text(resp) == "AB"

    def test_legacy_magicmock_blocks_still_work(self):
        """既存テストの MagicMock(text=...) 形式のモックも扱える"""
        resp = MagicMock()
        resp.content = [MagicMock(text="テスト応答")]
        assert extract_text(resp) == "テスト応答"

    def test_empty_content(self):
        assert extract_text(_response()) == ""
        assert extract_text(SimpleNamespace(content=None)) == ""

    def test_redacted_thinking_skipped(self):
        resp = _response(
            SimpleNamespace(type="redacted_thinking", data="..."),
            SimpleNamespace(type="text", text="了解でございます。"),
        )
        assert extract_text(resp) == "了解でございます。"


class TestDefaultModel:
    def test_client_uses_shared_default_model(self):
        from unittest.mock import patch

        from src.clients.claude import ClaudeClient

        with patch("src.clients.claude.anthropic.Anthropic"):
            client = ClaudeClient(api_key="test")
        assert client.model == DEFAULT_CLAUDE_MODEL
        assert "20250514" not in DEFAULT_CLAUDE_MODEL
