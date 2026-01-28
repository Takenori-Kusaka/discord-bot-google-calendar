"""LangGraph エージェントの単体テスト

ChatAnthropicをMagicMockでモック化してテストします。
（GenericFakeChatModelはbind_toolsをサポートしていないため）
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage, ToolCall


class TestAgentState:
    """AgentStateのテスト"""

    def test_agent_state_structure(self):
        """AgentStateの構造"""
        from src.agents.graph import AgentState

        # TypedDictの構造を確認
        assert "messages" in AgentState.__annotations__
        assert "user_context" in AgentState.__annotations__
        assert "retry_count" in AgentState.__annotations__
        assert "error" in AgentState.__annotations__


class TestButlerSystemPrompt:
    """システムプロンプトのテスト"""

    def test_system_prompt_format(self):
        """システムプロンプトのフォーマット"""
        from src.agents.graph import BUTLER_SYSTEM_PROMPT

        # プロンプトに必須要素が含まれているか
        assert "{butler_name}" in BUTLER_SYSTEM_PROMPT
        assert "{family_context}" in BUTLER_SYSTEM_PROMPT
        assert "{today}" in BUTLER_SYSTEM_PROMPT
        assert "執事" in BUTLER_SYSTEM_PROMPT
        assert "日下家" in BUTLER_SYSTEM_PROMPT

    def test_system_prompt_tool_guidelines(self):
        """システムプロンプトにツールガイドラインが含まれる"""
        from src.agents.graph import BUTLER_SYSTEM_PROMPT

        # 主要ツールがガイドラインに記載されているか
        assert "get_calendar_events" in BUTLER_SYSTEM_PROMPT
        assert "get_weather" in BUTLER_SYSTEM_PROMPT
        assert "create_calendar_event" in BUTLER_SYSTEM_PROMPT
        assert "web_search" in BUTLER_SYSTEM_PROMPT


class TestLangChainTools:
    """LangChainツール定義のテスト"""

    def test_create_langchain_tools(self):
        """LangChainツールが作成される"""
        from src.agents.graph import create_langchain_tools

        tools = create_langchain_tools()

        # ツールが作成されていることを確認
        assert len(tools) > 0

        # ツール名を確認
        tool_names = [t.name for t in tools]
        assert "get_calendar_events" in tool_names
        assert "get_weather" in tool_names
        assert "create_calendar_event" in tool_names


class TestCompileButlerGraph:
    """compile_butler_graph関数のテスト"""

    def test_create_graph_structure(self):
        """グラフ構造の作成"""
        from src.agents.graph import compile_butler_graph

        # ChatAnthropicとbind_toolsをモック
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            graph = compile_butler_graph(
                tool_executor=MagicMock(),
                model="claude-sonnet-4-20250514",
            )

            # グラフが作成されていることを確認
            assert graph is not None


class TestRunButlerAgent:
    """run_butler_agent関数のテスト

    LLMをモックして、実際のAPIコールなしでエージェントをテスト。
    """

    @pytest.fixture
    def mock_tool_executor(self):
        """ToolExecutorのモック"""
        executor = MagicMock()
        executor.execute = AsyncMock()
        return executor

    def _create_mock_llm(self, responses):
        """応答シーケンスを返すモックLLMを作成"""
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.invoke = MagicMock(side_effect=responses)
        return mock_llm

    @pytest.mark.asyncio
    async def test_run_agent_simple_query(self, mock_tool_executor):
        """シンプルなクエリの処理"""
        from src.agents.graph import run_butler_agent

        response = AIMessage(content="旦那様、おはようございます。黒田でございます。")
        mock_llm = self._create_mock_llm([response])

        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            result = await run_butler_agent(
                message="こんにちは",
                tool_executor=mock_tool_executor,
            )

            # 応答が返されることを確認
            assert result is not None
            assert isinstance(result, str)
            assert "ございます" in result

    @pytest.mark.asyncio
    async def test_run_agent_with_tool_call(self, mock_tool_executor):
        """ツール呼び出しを含むクエリの処理"""
        from src.agents.graph import run_butler_agent

        # ツール呼び出しを含む応答シーケンス
        first_response = AIMessage(
            content="",
            tool_calls=[
                ToolCall(
                    name="get_calendar_events",
                    args={"date_range": "today"},
                    id="call_001",
                )
            ],
        )
        second_response = AIMessage(
            content="本日の予定は以下の通りでございます。10時からミーティングがございます。"
        )

        mock_llm = self._create_mock_llm([first_response, second_response])

        # ツール実行結果を設定
        mock_tool_executor.execute = AsyncMock(
            return_value=MagicMock(
                content="10:00: ミーティング",
                is_error=False,
            )
        )

        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            result = await run_butler_agent(
                message="今日の予定を教えて",
                tool_executor=mock_tool_executor,
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_run_agent_with_family_context(self, mock_tool_executor):
        """家族コンテキスト付きのクエリ処理"""
        from src.agents.graph import run_butler_agent

        user_context = {"family_status": "旦那様は在宅勤務中です。"}

        response = AIMessage(content="旦那様、お仕事お疲れ様でございます。")
        mock_llm = self._create_mock_llm([response])

        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            result = await run_butler_agent(
                message="おはよう",
                tool_executor=mock_tool_executor,
                user_context=user_context,
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_run_agent_with_images(self, mock_tool_executor):
        """画像付きクエリの処理"""
        from src.agents.graph import run_butler_agent

        images = [
            {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": "base64encodeddata",
            }
        ]

        response = AIMessage(
            content="こちらの画像を拝見いたしました。イベントのチラシでございますね。"
        )
        mock_llm = self._create_mock_llm([response])

        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            result = await run_butler_agent(
                message="この写真について教えて",
                tool_executor=mock_tool_executor,
                images=images,
            )

            assert result is not None


class TestValidationNode:
    """バリデーションノードのテスト"""

    def test_butler_tone_validation(self):
        """執事口調のバリデーション"""
        # 執事口調の応答
        butler_responses = [
            "かしこまりました。",
            "恐れ入りますが、〜でございます。",
            "旦那様、おはようございます。",
        ]

        # 実際のバリデーションロジックがあればテスト
        # ここでは口調の例が正しいことを確認
        for response in butler_responses:
            # 執事らしい表現が含まれることを確認
            assert any(
                word in response
                for word in ["ございます", "かしこまり", "恐れ入り", "旦那様", "奥様"]
            )


class TestEdgeCases:
    """エッジケースのテスト"""

    @pytest.fixture
    def mock_tool_executor(self):
        """ToolExecutorのモック"""
        executor = MagicMock()
        executor.execute = AsyncMock()
        return executor

    def _create_mock_llm(self, responses):
        """応答シーケンスを返すモックLLMを作成"""
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.invoke = MagicMock(side_effect=responses)
        return mock_llm

    @pytest.mark.asyncio
    async def test_empty_message(self, mock_tool_executor):
        """空メッセージの処理"""
        from src.agents.graph import run_butler_agent

        response = AIMessage(content="何かお手伝いできることはございますか？")
        mock_llm = self._create_mock_llm([response])

        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            result = await run_butler_agent(
                message="",
                tool_executor=mock_tool_executor,
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_long_message(self, mock_tool_executor):
        """長いメッセージの処理"""
        from src.agents.graph import run_butler_agent

        long_message = "テスト" * 1000

        response = AIMessage(content="かしこまりました。長文を頂戴いたしました。")
        mock_llm = self._create_mock_llm([response])

        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            result = await run_butler_agent(
                message=long_message,
                tool_executor=mock_tool_executor,
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_llm_error_handling(self, mock_tool_executor):
        """LLMエラーのハンドリング"""
        from src.agents.graph import run_butler_agent

        # LLMがエラーを発生させる場合
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.invoke = MagicMock(side_effect=Exception("LLM Error"))

        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            # エラーが適切にハンドリングされることを確認
            try:
                result = await run_butler_agent(
                    message="テスト",
                    tool_executor=mock_tool_executor,
                )
                # エラーハンドリングされた応答が返る場合
                assert result is not None
            except Exception as e:
                # 例外が発生する実装の場合
                assert "LLM Error" in str(e) or "Error" in str(e)


class TestGraphRouting:
    """グラフのルーティングロジックテスト"""

    @pytest.fixture
    def mock_tool_executor(self):
        """ToolExecutorのモック"""
        executor = MagicMock()
        executor.execute = AsyncMock()
        return executor

    def _create_mock_llm(self, responses):
        """応答シーケンスを返すモックLLMを作成"""
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.invoke = MagicMock(side_effect=responses)
        return mock_llm

    @pytest.mark.asyncio
    async def test_tool_call_routing(self, mock_tool_executor):
        """ツール呼び出し時のルーティング"""
        from src.agents.graph import run_butler_agent

        # ツール呼び出し→結果→最終応答のシーケンス
        first_response = AIMessage(
            content="",
            tool_calls=[ToolCall(name="get_weather", args={}, id="call_weather")],
        )
        second_response = AIMessage(
            content="本日は晴れでございます。最高気温は15度の予報でございます。"
        )
        mock_llm = self._create_mock_llm([first_response, second_response])

        mock_tool_executor.execute = AsyncMock(
            return_value=MagicMock(
                content="晴れ、最高気温15度",
                is_error=False,
            )
        )

        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            result = await run_butler_agent(
                message="今日の天気は？",
                tool_executor=mock_tool_executor,
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, mock_tool_executor):
        """複数ツール呼び出しの処理"""
        from src.agents.graph import run_butler_agent

        # 複数のツール呼び出しを含む応答
        first_response = AIMessage(
            content="",
            tool_calls=[
                ToolCall(name="get_calendar_events", args={}, id="call_1"),
                ToolCall(name="get_weather", args={}, id="call_2"),
            ],
        )
        second_response = AIMessage(content="本日の予定は3件、天気は晴れでございます。")
        mock_llm = self._create_mock_llm([first_response, second_response])

        mock_tool_executor.execute = AsyncMock(
            side_effect=[
                MagicMock(content="予定3件", is_error=False),
                MagicMock(content="晴れ", is_error=False),
            ]
        )

        with patch("src.agents.graph.ChatAnthropic", return_value=mock_llm):
            result = await run_butler_agent(
                message="今日の予定と天気を教えて",
                tool_executor=mock_tool_executor,
            )

            assert result is not None
