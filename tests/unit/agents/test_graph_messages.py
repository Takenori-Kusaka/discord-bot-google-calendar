"""LangGraph エージェントのメッセージ処理テスト

Claude Sonnet 5.5 以降（adaptive thinking 既定ON）で AIMessage.content が
thinking ブロックを含むリストになるケース、およびシステムプロンプトが
実際にモデルへ渡されることを検証する。
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.config.settings import DEFAULT_CLAUDE_MODEL

THINKING_BLOCK = {"type": "thinking", "thinking": "...", "signature": "sig"}


class TestMessageText:
    """message_text() のテスト"""

    def test_plain_string(self):
        from src.agents.graph import message_text

        assert message_text("かしこまりました。") == "かしこまりました。"

    def test_list_with_thinking_block_first(self):
        from src.agents.graph import message_text

        content = [
            THINKING_BLOCK,
            {"type": "text", "text": "かしこまりました。"},
            {"type": "text", "text": "ただいまお調べいたします。"},
        ]
        assert message_text(content) == "かしこまりました。ただいまお調べいたします。"

    def test_list_of_strings(self):
        from src.agents.graph import message_text

        assert message_text(["a", "b"]) == "ab"

    def test_empty_and_none(self):
        from src.agents.graph import message_text

        assert message_text([]) == ""
        assert message_text(None) == ""
        assert message_text([THINKING_BLOCK]) == ""


class TestAgentNodeSystemPrompt:
    """agent_node がシステムプロンプトを SystemMessage として渡すこと"""

    def _config(self, mock_llm):
        from src.agents.graph import ButlerGraphConfig

        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            return ButlerGraphConfig(tool_executor=MagicMock(), butler_name="黒田")

    def test_system_message_is_first(self):
        from src.agents.graph import agent_node, set_config

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.invoke = MagicMock(
            return_value=AIMessage(content="はい、でございます。")
        )
        set_config(self._config(mock_llm))

        state = {
            "messages": [HumanMessage(content="おはよう")],
            "user_context": {"family_context": "旦那様: テスト"},
            "retry_count": 0,
            "error": None,
        }
        result = agent_node(state)

        assert result["error"] is None
        args, kwargs = mock_llm.invoke.call_args
        messages = args[0]
        assert isinstance(messages[0], SystemMessage)
        assert "執事" in messages[0].content
        assert "黒田" in messages[0].content
        assert "旦那様: テスト" in messages[0].content
        assert isinstance(messages[1], HumanMessage)
        # 旧実装（ChatAnthropic が無視する configurable 経由）に戻っていないこと
        assert "config" not in kwargs

    def test_system_message_not_persisted_in_state(self):
        """SystemMessage は毎回先頭に付与し、state には蓄積しない"""
        from src.agents.graph import agent_node, set_config

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.invoke = MagicMock(
            return_value=AIMessage(content="はい、でございます。")
        )
        set_config(self._config(mock_llm))

        result = agent_node(
            {
                "messages": [HumanMessage(content="おはよう")],
                "user_context": {},
                "retry_count": 0,
                "error": None,
            }
        )
        assert all(not isinstance(m, SystemMessage) for m in result["messages"])


class TestValidationWithThinkingBlocks:
    """validation_node が thinking ブロック混在の content を扱えること"""

    def _set_config(self):
        from src.agents.graph import ButlerGraphConfig, set_config

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            set_config(ButlerGraphConfig(tool_executor=MagicMock(), butler_name="黒田"))

    def test_butler_tone_detected_in_list_content(self):
        from src.agents.graph import validation_node

        self._set_config()
        state = {
            "messages": [
                HumanMessage(content="おはよう"),
                AIMessage(
                    content=[
                        THINKING_BLOCK,
                        {"type": "text", "text": "旦那様、おはようございます。"},
                    ]
                ),
            ],
            "user_context": {},
            "retry_count": 0,
            "error": None,
        }
        result = validation_node(state)
        assert result["error"] is None
        assert "retry_count" not in result

    def test_missing_tone_requests_retry(self):
        from src.agents.graph import validation_node

        self._set_config()
        state = {
            "messages": [
                HumanMessage(content="おはよう"),
                AIMessage(
                    content=[THINKING_BLOCK, {"type": "text", "text": "おはよう！"}]
                ),
            ],
            "user_context": {},
            "retry_count": 0,
            "error": None,
        }
        result = validation_node(state)
        assert result["retry_count"] == 1
        assert isinstance(result["messages"][0], HumanMessage)


class TestRunButlerAgentModel:
    """run_butler_agent のモデル指定と list content の扱い"""

    def _mock_llm(self, responses):
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.invoke = MagicMock(side_effect=responses)
        return mock_llm

    @pytest.mark.asyncio
    async def test_model_is_passed_to_chat_anthropic(self):
        from src.agents.graph import run_butler_agent

        mock_llm = self._mock_llm([AIMessage(content="はい、でございます。")])
        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm) as chat:
            await run_butler_agent(
                "こんにちは", tool_executor=MagicMock(), model="my-model"
            )
        assert chat.call_args.kwargs["model"] == "my-model"

    @pytest.mark.asyncio
    async def test_default_model_when_not_specified(self):
        from src.agents.graph import run_butler_agent

        mock_llm = self._mock_llm([AIMessage(content="はい、でございます。")])
        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm) as chat:
            await run_butler_agent("こんにちは", tool_executor=MagicMock())
        assert chat.call_args.kwargs["model"] == DEFAULT_CLAUDE_MODEL

    @pytest.mark.asyncio
    async def test_returns_plain_text_for_list_content(self):
        """最終応答が list content でも Discord に送れる str を返す"""
        from src.agents.graph import run_butler_agent

        mock_llm = self._mock_llm(
            [
                AIMessage(
                    content=[
                        THINKING_BLOCK,
                        {
                            "type": "text",
                            "text": "かしこまりました。青色でございます。",
                        },
                    ]
                )
            ]
        )
        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            result = await run_butler_agent("色は？", tool_executor=MagicMock())
        assert result == "かしこまりました。青色でございます。"
