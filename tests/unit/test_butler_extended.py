"""Butler コアクラスの拡張テスト

既存のtest_butler.pyを補完し、追加のユースケースをカバーします。
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from src.butler import Butler
from src.clients.calendar import CalendarEvent
from src.clients.weather import WeatherInfo


class TestButlerInitialization:
    """Butler初期化のテスト"""

    def test_butler_initialization_minimal(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """最小構成での初期化"""
        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        assert butler.name == "黒田"
        assert butler.calendar == mock_calendar_client
        assert butler.claude == mock_claude_client
        assert butler.discord == mock_discord_client
        mock_discord_client.set_message_handler.assert_called_once()

    def test_butler_initialization_full(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
        mock_weather_client,
        mock_event_search_client,
        mock_today_info_client,
        mock_life_info_client,
        mock_reminder_client,
        mock_shopping_list_client,
        mock_housework_client,
        mock_home_assistant_client,
        mock_expense_client,
    ):
        """全クライアント指定での初期化"""
        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                weather_client=mock_weather_client,
                event_search_client=mock_event_search_client,
                today_info_client=mock_today_info_client,
                life_info_client=mock_life_info_client,
                reminder_client=mock_reminder_client,
                shopping_list_client=mock_shopping_list_client,
                housework_client=mock_housework_client,
                home_assistant_client=mock_home_assistant_client,
                expense_client=mock_expense_client,
            )

        assert butler.weather == mock_weather_client
        assert butler.event_search == mock_event_search_client

    def test_butler_initialization_langgraph_mode(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """LangGraphモードでの初期化"""
        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                use_langgraph=True,
            )

        assert butler.use_langgraph is True


class TestMorningNotificationWithWeather:
    """天気情報付き朝の通知テスト"""

    @pytest.mark.asyncio
    async def test_morning_notification_with_weather(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
        mock_weather_client,
        sample_events,
        sample_weather,
    ):
        """天気情報付きの朝の通知"""
        # Arrange
        mock_calendar_client.get_today_events.return_value = sample_events
        mock_claude_client.filter_important_events.return_value = [sample_events[0]]
        mock_claude_client.generate_butler_message.return_value = "テストメッセージ"
        mock_weather_client.get_today_weather.return_value = sample_weather

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                weather_client=mock_weather_client,
            )

        # Act
        await butler.morning_notification()

        # Assert
        mock_weather_client.get_today_weather.assert_called_once()
        call_args = mock_discord_client.send_to_channel.call_args[0][1]
        assert "天気" in call_args


class TestMorningNotificationWithTodayInfo:
    """今日は何の日付き朝の通知テスト"""

    @pytest.mark.asyncio
    async def test_morning_notification_with_today_info(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
        mock_today_info_client,
        sample_events,
    ):
        """今日は何の日付きの朝の通知"""
        # Arrange
        mock_calendar_client.get_today_events.return_value = sample_events
        mock_claude_client.filter_important_events.return_value = [sample_events[0]]
        mock_claude_client.generate_butler_message.return_value = "テストメッセージ"

        # 今日は何の日のモック
        today_info = MagicMock()
        today_info.format_for_notification.return_value = "今日は文化の日です"
        mock_today_info_client.get_today_info.return_value = today_info

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                today_info_client=mock_today_info_client,
            )

        # Act
        await butler.morning_notification()

        # Assert
        mock_today_info_client.get_today_info.assert_called_once()
        call_args = mock_discord_client.send_to_channel.call_args[0][1]
        assert "豆知識" in call_args


class TestWeeklyEventNotification:
    """週次イベント通知のテスト"""

    @pytest.mark.asyncio
    async def test_weekly_event_fallback_to_reference(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
        mock_event_search_client,
    ):
        """イベント抽出失敗時のフォールバック"""
        # Arrange
        mock_settings.discord_channel_region = "地域のこと"
        mock_event_search_client.search_events.return_value = [
            {"title": "テスト", "snippet": "内容"}
        ]
        mock_claude_client.extract_events_from_search.return_value = []
        mock_event_search_client.build_events_from_results.return_value = [
            {"title": "フォールバックイベント"}
        ]
        mock_claude_client.generate_event_recommendation.return_value = "週末のおすすめ"

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                event_search_client=mock_event_search_client,
            )

        # Act
        await butler.weekly_event_notification()

        # Assert
        mock_event_search_client.build_events_from_results.assert_called_once()

    @pytest.mark.asyncio
    async def test_weekly_event_duplicate_skip(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
        mock_event_search_client,
    ):
        """重複メッセージのスキップ"""
        # Arrange
        mock_settings.discord_channel_region = "地域のこと"
        mock_event_search_client.search_events.return_value = [{"title": "イベント"}]
        mock_claude_client.extract_events_from_search.return_value = [
            {"title": "お祭り"}
        ]
        mock_claude_client.generate_event_recommendation.return_value = "週末のおすすめ"
        mock_discord_client.is_duplicate_message.return_value = True

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                event_search_client=mock_event_search_client,
            )

        # Act
        await butler.weekly_event_notification()

        # Assert
        # 重複の場合、send_to_channelは呼ばれない
        mock_discord_client.send_to_channel.assert_not_called()


class TestWeeklyLifeInfoNotification:
    """週次生活影響情報通知のテスト"""

    @pytest.mark.asyncio
    async def test_weekly_life_info_success(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
        mock_life_info_client,
    ):
        """生活影響情報通知の正常系"""
        # Arrange
        mock_settings.discord_channel_region = "地域のこと"
        mock_life_info_client.get_all_life_info.return_value = [
            {"title": "児童手当増額", "description": "来月から増額"}
        ]
        mock_life_info_client.format_for_weekly_notification.return_value = (
            "【生活影響情報】児童手当が増額されます"
        )

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                life_info_client=mock_life_info_client,
            )

        # Act
        await butler.weekly_life_info_notification()

        # Assert
        mock_life_info_client.get_all_life_info.assert_called_once()
        mock_discord_client.send_to_channel.assert_called_once()

    @pytest.mark.asyncio
    async def test_weekly_life_info_no_items(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
        mock_life_info_client,
    ):
        """生活影響情報がない場合"""
        # Arrange
        mock_life_info_client.get_all_life_info.return_value = []

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                life_info_client=mock_life_info_client,
            )

        # Act
        await butler.weekly_life_info_notification()

        # Assert
        mock_discord_client.send_to_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_weekly_life_info_no_client(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """クライアント未設定時"""
        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                life_info_client=None,
            )

        # Act
        await butler.weekly_life_info_notification()

        # Assert
        mock_discord_client.send_to_channel.assert_not_called()


class TestHandleMessage:
    """メッセージハンドリングのテスト"""

    @pytest.mark.asyncio
    async def test_handle_message_claude_mode(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """Claude直接モードでのメッセージ処理"""
        # Arrange
        mock_claude_client.chat_with_tools.return_value = "かしこまりました"

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                use_langgraph=False,
            )

        # Act
        response = await butler.handle_message("今日の予定は？", "予定")

        # Assert
        assert response == "かしこまりました"
        mock_claude_client.chat_with_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_langgraph_mode(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """LangGraphモードでのメッセージ処理"""
        # Arrange
        with (
            patch("src.butler.Path.exists", return_value=False),
            patch("src.butler.run_butler_agent") as mock_run_agent,
        ):
            mock_run_agent.return_value = "かしこまりました（LangGraph）"

            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                use_langgraph=True,
            )

            # Act
            response = await butler.handle_message("今日の予定は？", "予定")

            # Assert
            assert "LangGraph" in response
            mock_run_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_with_images(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """画像付きメッセージの処理"""
        # Arrange
        mock_claude_client.chat_with_tools.return_value = "この画像は..."
        images = [{"type": "base64", "media_type": "image/jpeg", "data": "base64data"}]

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        # Act
        response = await butler.handle_message("この画像は何？", "雑談", images=images)

        # Assert
        assert response is not None

    @pytest.mark.asyncio
    async def test_handle_message_error(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """メッセージ処理エラー時"""
        # Arrange
        mock_claude_client.chat_with_tools.side_effect = Exception("API Error")

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        # Act
        response = await butler.handle_message("テスト", "雑談")

        # Assert
        assert "エラー" in response
        assert "黒田" in response


class TestFamilyContext:
    """家族コンテキストのテスト"""

    def test_get_family_context_with_data(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """家族データがある場合"""
        family_yaml = """
garbage:
  schedule:
    - type: 燃えるごみ
      days: 月・木
location:
  favorite_places:
    - name: イオンモール高の原
      type: ショッピング
"""
        with (
            patch("src.butler.Path.exists", return_value=True),
            patch("builtins.open", MagicMock()),
            patch("yaml.safe_load") as mock_yaml,
        ):
            mock_yaml.return_value = {
                "garbage": {"schedule": [{"type": "燃えるごみ", "days": "月・木"}]},
                "location": {
                    "favorite_places": [
                        {"name": "イオンモール", "type": "ショッピング"}
                    ]
                },
            }

            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

            context = butler._get_family_context()

            assert "ごみ捨て" in context or "燃えるごみ" in context

    def test_get_family_context_empty(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """家族データがない場合"""
        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        context = butler._get_family_context()
        assert context == ""


class TestStateManagement:
    """状態管理のテスト"""

    def test_load_state_empty(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
        tmp_path,
    ):
        """状態ファイルがない場合"""
        # tmp_pathを使用して一時的なディレクトリに状態を保存
        mock_settings.log_dir = tmp_path

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        # tmp_pathを使っているので、存在しないファイルは空の辞書を返す
        state = butler._load_state()
        assert state == {}

    def test_weekly_event_key(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """週次イベントキーの生成"""
        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        tz = ZoneInfo("Asia/Tokyo")
        now = datetime(2026, 1, 24, 12, 0, tzinfo=tz)
        key = butler._weekly_event_key(now)

        # ISO週番号を含むキー
        assert "2026-W" in key

    def test_hash_message(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """メッセージハッシュの生成"""
        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        hash1 = butler._hash_message("テストメッセージ")
        hash2 = butler._hash_message("テストメッセージ")
        hash3 = butler._hash_message("別のメッセージ")

        assert hash1 == hash2
        assert hash1 != hash3
