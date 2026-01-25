"""Claude クライアントの単体テスト"""

import pytest
import json
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock
from zoneinfo import ZoneInfo

from src.clients.claude import ClaudeClient
from src.clients.calendar import CalendarEvent


class TestClaudeClient:
    """ClaudeClientクラスのテスト"""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Anthropicクライアントのモック"""
        mock = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="テスト応答")]
        mock.messages.create.return_value = mock_response
        return mock

    @pytest.fixture
    def claude_client(self, mock_anthropic_client):
        """ClaudeClientのインスタンス（モック済み）"""
        with patch("src.clients.claude.anthropic.Anthropic") as mock_class:
            mock_class.return_value = mock_anthropic_client
            client = ClaudeClient(
                api_key="test-api-key",
                model="claude-sonnet-4-20250514",
            )
            client.client = mock_anthropic_client
            return client

    @pytest.fixture
    def sample_events(self):
        """サンプルイベント"""
        tz = ZoneInfo("Asia/Tokyo")
        return [
            CalendarEvent(
                id="event-001",
                summary="病院予約",
                start=datetime(2026, 1, 24, 10, 0, tzinfo=tz),
                end=datetime(2026, 1, 24, 11, 0, tzinfo=tz),
                location="木津川市立病院",
            ),
            CalendarEvent(
                id="event-002",
                summary="仕事",
                start=datetime(2026, 1, 24, 9, 0, tzinfo=tz),
                end=datetime(2026, 1, 24, 18, 0, tzinfo=tz),
            ),
        ]


class TestFilterImportantEvents(TestClaudeClient):
    """filter_important_eventsメソッドのテスト"""

    @pytest.mark.asyncio
    async def test_filter_important_events_success(
        self, claude_client, mock_anthropic_client, sample_events
    ):
        """重要なイベントをフィルタリング"""
        # モックレスポンス - IDリストを返す
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='["event-001"]')]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await claude_client.filter_important_events(
            sample_events,
            ignore_patterns=["仕事"],
            notify_patterns=["病院"],
        )

        assert len(result) == 1
        assert result[0].id == "event-001"
        assert result[0].summary == "病院予約"

    @pytest.mark.asyncio
    async def test_filter_important_events_empty_list(self, claude_client):
        """空のリストの場合は空を返す"""
        result = await claude_client.filter_important_events([])
        assert result == []

    @pytest.mark.asyncio
    async def test_filter_important_events_all_filtered(
        self, claude_client, mock_anthropic_client, sample_events
    ):
        """すべてフィルタされた場合"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="[]")]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await claude_client.filter_important_events(sample_events)

        assert result == []

    @pytest.mark.asyncio
    async def test_filter_important_events_api_error(
        self, claude_client, mock_anthropic_client, sample_events
    ):
        """APIエラー時は全イベントを返す"""
        mock_anthropic_client.messages.create.side_effect = Exception("API Error")

        result = await claude_client.filter_important_events(sample_events)

        # エラー時は全イベントを返す
        assert len(result) == len(sample_events)

    @pytest.mark.asyncio
    async def test_filter_important_events_invalid_json(
        self, claude_client, mock_anthropic_client, sample_events
    ):
        """不正なJSON応答の場合"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="重要なイベントは見つかりませんでした")]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await claude_client.filter_important_events(sample_events)

        # JSONが見つからない場合は空リスト
        assert result == []


class TestGenerateButlerMessage(TestClaudeClient):
    """generate_butler_messageメソッドのテスト"""

    @pytest.mark.asyncio
    async def test_generate_butler_message_success(
        self, claude_client, mock_anthropic_client, sample_events
    ):
        """メッセージ生成成功"""
        expected_message = "旦那様、おはようございます。執事の黒田でございます。"
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=expected_message)]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await claude_client.generate_butler_message(
            sample_events,
            butler_name="黒田",
        )

        assert "旦那様" in result
        assert "黒田" in result

    @pytest.mark.asyncio
    async def test_generate_butler_message_no_events(self, claude_client):
        """予定がない場合のメッセージ"""
        result = await claude_client.generate_butler_message(
            [],
            butler_name="黒田",
        )

        assert "予定は特にございません" in result or "ございません" in result

    @pytest.mark.asyncio
    async def test_generate_butler_message_api_error(
        self, claude_client, mock_anthropic_client, sample_events
    ):
        """APIエラー時のフォールバック"""
        mock_anthropic_client.messages.create.side_effect = Exception("API Error")

        result = await claude_client.generate_butler_message(
            sample_events,
            butler_name="黒田",
        )

        # エラー時もメッセージが返る（フォールバック）
        assert "旦那様" in result
        assert "黒田" in result


class TestExtractEventsFromSearch(TestClaudeClient):
    """extract_events_from_searchメソッドのテスト"""

    @pytest.fixture
    def sample_search_results(self):
        """サンプル検索結果"""
        return [
            {
                "query": "木津川市 イベント",
                "title": "高の原マルシェ",
                "snippet": "1/25(土) 高の原駅前広場にて開催",
                "link": "https://example.com/event1",
            },
            {
                "query": "奈良 子供向け",
                "title": "子育てフェスタ",
                "snippet": "家族で楽しめるイベント",
                "link": "https://example.com/event2",
            },
        ]

    @pytest.mark.asyncio
    async def test_extract_events_success(
        self, claude_client, mock_anthropic_client, sample_search_results
    ):
        """イベント抽出成功"""
        mock_events = [
            {
                "title": "高の原マルシェ",
                "date": "1/25(土) 10:00〜",
                "location": "高の原駅前",
                "description": "地元の特産品が並ぶマルシェ",
                "target_audience": "全年齢",
                "url": "https://example.com/event1",
            }
        ]
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(mock_events))]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await claude_client.extract_events_from_search(sample_search_results)

        assert len(result) == 1
        assert result[0]["title"] == "高の原マルシェ"

    @pytest.mark.asyncio
    async def test_extract_events_empty_results(self, claude_client):
        """空の検索結果"""
        result = await claude_client.extract_events_from_search([])
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_events_api_error(
        self, claude_client, mock_anthropic_client, sample_search_results
    ):
        """APIエラー時は空リストを返す"""
        mock_anthropic_client.messages.create.side_effect = Exception("API Error")

        result = await claude_client.extract_events_from_search(sample_search_results)

        assert result == []


class TestGenerateEventRecommendation(TestClaudeClient):
    """generate_event_recommendationメソッドのテスト"""

    @pytest.fixture
    def sample_events_dict(self):
        """サンプルイベント（辞書形式）"""
        return [
            {
                "title": "高の原マルシェ",
                "date": "1/25(土) 10:00〜",
                "location": "高の原駅前",
                "description": "地元の特産品が並ぶマルシェ",
            }
        ]

    @pytest.mark.asyncio
    async def test_generate_recommendation_success(
        self, claude_client, mock_anthropic_client, sample_events_dict
    ):
        """おすすめメッセージ生成成功"""
        expected = "旦那様、奥様、執事の黒田でございます。今週末のイベント..."
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=expected)]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await claude_client.generate_event_recommendation(
            sample_events_dict,
            butler_name="黒田",
        )

        assert "旦那様" in result or "黒田" in result

    @pytest.mark.asyncio
    async def test_generate_recommendation_no_events(self, claude_client):
        """イベントがない場合"""
        result = await claude_client.generate_event_recommendation(
            [],
            butler_name="黒田",
        )

        assert "見つかりませんでした" in result or "ございません" in result

    @pytest.mark.asyncio
    async def test_generate_recommendation_api_error(
        self, claude_client, mock_anthropic_client, sample_events_dict
    ):
        """APIエラー時のフォールバック"""
        mock_anthropic_client.messages.create.side_effect = Exception("API Error")

        result = await claude_client.generate_event_recommendation(
            sample_events_dict,
            butler_name="黒田",
        )

        # フォールバックメッセージ
        assert "黒田" in result


class TestConversationHistory(TestClaudeClient):
    """会話履歴管理のテスト"""

    def test_get_conversation_history_new_channel(self, claude_client):
        """新しいチャンネルの会話履歴"""
        history = claude_client._get_conversation_history("test-channel")
        assert len(history) == 0

    def test_add_to_history(self, claude_client):
        """会話履歴への追加"""
        claude_client._add_to_history("test-channel", "user", "こんにちは")
        claude_client._add_to_history("test-channel", "assistant", "はい、旦那様")

        history = claude_client._get_conversation_history("test-channel")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    def test_clear_conversation_history_specific_channel(self, claude_client):
        """特定チャンネルの履歴クリア"""
        claude_client._add_to_history("channel-1", "user", "メッセージ1")
        claude_client._add_to_history("channel-2", "user", "メッセージ2")

        claude_client.clear_conversation_history("channel-1")

        assert len(claude_client._get_conversation_history("channel-1")) == 0
        assert len(claude_client._get_conversation_history("channel-2")) == 1

    def test_clear_conversation_history_all(self, claude_client):
        """全チャンネルの履歴クリア"""
        claude_client._add_to_history("channel-1", "user", "メッセージ1")
        claude_client._add_to_history("channel-2", "user", "メッセージ2")

        claude_client.clear_conversation_history()

        assert len(claude_client._get_conversation_history("channel-1")) == 0
        assert len(claude_client._get_conversation_history("channel-2")) == 0

    def test_conversation_history_max_limit(self, claude_client):
        """会話履歴の最大数制限"""
        # MAX_CONVERSATION_HISTORY = 10 を超えるメッセージを追加
        for i in range(15):
            claude_client._add_to_history("test-channel", "user", f"メッセージ{i}")

        history = claude_client._get_conversation_history("test-channel")
        assert len(history) == 10  # 最大10件
