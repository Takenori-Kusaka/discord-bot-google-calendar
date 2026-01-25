"""統合テスト - 朝の通知フロー

複数クライアントが連携する朝の通知フローをテストします。
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from src.butler import Butler
from src.clients.calendar import CalendarEvent
from src.clients.weather import WeatherInfo


class TestMorningNotificationFlow:
    """朝の通知フロー統合テスト"""

    @pytest.fixture
    def mock_settings(self):
        """設定のモック"""
        settings = MagicMock()
        settings.butler_name = "黒田"
        settings.discord_channel_schedule = "予定"
        settings.timezone = "Asia/Tokyo"
        settings.log_dir = None
        return settings

    @pytest.fixture
    def mock_calendar_client(self):
        """カレンダークライアントのモック"""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_claude_client(self):
        """Claudeクライアントのモック"""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_discord_client(self):
        """Discordクライアントのモック"""
        client = AsyncMock()
        client.send_to_channel = AsyncMock(return_value=True)
        client.send_error_notification = AsyncMock(return_value=True)
        client.set_message_handler = MagicMock()
        return client

    @pytest.fixture
    def mock_weather_client(self):
        """天気クライアントのモック"""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_today_info_client(self):
        """今日は何の日クライアントのモック"""
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_full_morning_notification_flow(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
        mock_weather_client,
        mock_today_info_client,
    ):
        """完全な朝の通知フロー

        1. カレンダーから今日の予定を取得
        2. 重要な予定をフィルタリング
        3. 天気情報を取得
        4. 今日は何の日を取得
        5. 執事口調のメッセージを生成
        6. Discordに送信
        """
        # Arrange
        tz = ZoneInfo("Asia/Tokyo")
        sample_events = [
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
            CalendarEvent(
                id="event-003",
                summary="保護者会",
                start=datetime(2026, 1, 24, 14, 0, tzinfo=tz),
                end=datetime(2026, 1, 24, 16, 0, tzinfo=tz),
                location="精華小学校",
            ),
        ]

        # フィルタリング後の重要な予定
        important_events = [sample_events[0], sample_events[2]]

        # 天気情報
        sample_weather = WeatherInfo(
            date=datetime(2026, 1, 24, tzinfo=tz),
            weather_code=1,
            weather_description="晴れ",
            temperature_max=12.0,
            temperature_min=3.0,
            precipitation_probability=10,
            precipitation_sum=0.0,
        )

        # 今日は何の日
        today_info = MagicMock()
        today_info.format_for_notification.return_value = "今日は「郵便制度施行記念日」です"

        # モックの設定
        mock_calendar_client.get_today_events.return_value = sample_events
        mock_claude_client.filter_important_events.return_value = important_events
        mock_claude_client.generate_butler_message.return_value = (
            "旦那様、おはようございます。執事の黒田でございます。\n\n"
            "本日のご予定をお知らせいたします。\n"
            "- 10:00: 病院予約（木津川市立病院）\n"
            "- 14:00: 保護者会（精華小学校）\n\n"
            "どうぞお気をつけてお出かけくださいませ。"
        )
        mock_weather_client.get_today_weather.return_value = sample_weather
        mock_today_info_client.get_today_info.return_value = today_info

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                weather_client=mock_weather_client,
                today_info_client=mock_today_info_client,
            )

        # Act
        await butler.morning_notification()

        # Assert
        # 1. カレンダーから予定を取得
        mock_calendar_client.get_today_events.assert_called_once()

        # 2. 予定をフィルタリング
        mock_claude_client.filter_important_events.assert_called_once()
        call_args = mock_claude_client.filter_important_events.call_args[0][0]
        assert len(call_args) == 3

        # 3. 天気情報を取得
        mock_weather_client.get_today_weather.assert_called_once()

        # 4. 今日は何の日を取得
        mock_today_info_client.get_today_info.assert_called_once()

        # 5. メッセージを生成
        mock_claude_client.generate_butler_message.assert_called_once()

        # 6. Discordに送信
        mock_discord_client.send_to_channel.assert_called_once()
        channel_name, message = mock_discord_client.send_to_channel.call_args[0]
        assert channel_name == "予定"
        assert "黒田" in message
        assert "天気" in message
        assert "豆知識" in message

    @pytest.mark.asyncio
    async def test_morning_notification_calendar_error(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """カレンダー取得エラー時のフロー"""
        # Arrange
        mock_calendar_client.get_today_events.side_effect = Exception(
            "Calendar API Error"
        )

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        # Act
        await butler.morning_notification()

        # Assert
        # エラー通知が送信される
        mock_discord_client.send_error_notification.assert_called_once()
        error_arg = mock_discord_client.send_error_notification.call_args[0][0]
        assert "Calendar API Error" in str(error_arg)

    @pytest.mark.asyncio
    async def test_morning_notification_claude_filter_error(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """Claude フィルタリングエラー時のフロー"""
        # Arrange
        tz = ZoneInfo("Asia/Tokyo")
        sample_events = [
            CalendarEvent(
                id="event-001",
                summary="テスト",
                start=datetime(2026, 1, 24, 10, 0, tzinfo=tz),
                end=datetime(2026, 1, 24, 11, 0, tzinfo=tz),
            )
        ]
        mock_calendar_client.get_today_events.return_value = sample_events
        mock_claude_client.filter_important_events.side_effect = Exception(
            "Claude API Error"
        )

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        # Act
        await butler.morning_notification()

        # Assert
        mock_discord_client.send_error_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_morning_notification_discord_error(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """Discord送信エラー時のフロー"""
        # Arrange
        mock_calendar_client.get_today_events.return_value = []
        mock_claude_client.filter_important_events.return_value = []
        mock_claude_client.generate_butler_message.return_value = "テスト"
        mock_discord_client.send_to_channel.return_value = False

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        # Act
        await butler.morning_notification()

        # Assert
        # 送信失敗時もエラー通知
        mock_discord_client.send_error_notification.assert_called_once()


class TestWeeklyEventNotificationFlow:
    """週次イベント通知フロー統合テスト"""

    @pytest.fixture
    def mock_settings(self):
        """設定のモック"""
        settings = MagicMock()
        settings.butler_name = "黒田"
        settings.discord_channel_region = "地域のこと"
        settings.timezone = "Asia/Tokyo"
        settings.log_dir = None
        return settings

    @pytest.fixture
    def mock_calendar_client(self):
        """カレンダークライアントのモック"""
        return AsyncMock()

    @pytest.fixture
    def mock_claude_client(self):
        """Claudeクライアントのモック"""
        return AsyncMock()

    @pytest.fixture
    def mock_discord_client(self):
        """Discordクライアントのモック"""
        client = AsyncMock()
        client.send_to_channel = AsyncMock(return_value=True)
        client.send_error_notification = AsyncMock(return_value=True)
        client.set_message_handler = MagicMock()
        client.is_duplicate_message = AsyncMock(return_value=False)
        return client

    @pytest.fixture
    def mock_event_search_client(self):
        """イベント検索クライアントのモック"""
        client = AsyncMock()
        client.format_reference_links = MagicMock(return_value="")
        client.build_events_from_results = MagicMock(return_value=[])
        client.build_reference_events = MagicMock(return_value=[])
        return client

    @pytest.mark.asyncio
    async def test_full_weekly_event_flow(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
        mock_event_search_client,
    ):
        """完全な週次イベント通知フロー

        1. イベントを検索
        2. 検索結果からイベント情報を抽出
        3. 家族向けおすすめメッセージを生成
        4. 重複チェック
        5. Discordに送信
        """
        # Arrange
        search_results = [
            {
                "title": "高の原マルシェ",
                "snippet": "1/25(土) 高の原駅前広場にて開催",
                "link": "https://example.com/event1",
            },
            {
                "title": "木津川市 子育てフェスタ",
                "snippet": "家族で楽しめるイベント",
                "link": "https://example.com/event2",
            },
        ]

        extracted_events = [
            {
                "title": "高の原マルシェ",
                "date": "1/25(土) 10:00〜",
                "location": "高の原駅前",
                "description": "地元の特産品が並ぶマルシェ",
            }
        ]

        mock_event_search_client.search_events.return_value = search_results
        mock_claude_client.extract_events_from_search.return_value = extracted_events
        mock_claude_client.generate_event_recommendation.return_value = (
            "旦那様、奥様、執事の黒田でございます。\n\n"
            "今週末のイベント情報をお届けいたします。\n"
            "- 高の原マルシェ（1/25土 10:00〜）\n\n"
            "お嬢様も楽しめるイベントでございます。"
        )
        mock_event_search_client.format_reference_links.return_value = (
            "\n\n【参考リンク】\nhttps://example.com"
        )

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
        mock_event_search_client.search_events.assert_called_once()
        mock_claude_client.extract_events_from_search.assert_called_once()
        mock_claude_client.generate_event_recommendation.assert_called_once()
        mock_discord_client.send_to_channel.assert_called_once()

        channel_name, message = mock_discord_client.send_to_channel.call_args[0]
        assert channel_name == "地域のこと"
        assert "黒田" in message
        assert "参考リンク" in message


class TestMessageHandlingFlow:
    """メッセージハンドリングフロー統合テスト"""

    @pytest.fixture
    def mock_settings(self):
        """設定のモック"""
        settings = MagicMock()
        settings.butler_name = "黒田"
        settings.timezone = "Asia/Tokyo"
        settings.log_dir = None
        return settings

    @pytest.fixture
    def mock_calendar_client(self):
        """カレンダークライアントのモック"""
        return AsyncMock()

    @pytest.fixture
    def mock_claude_client(self):
        """Claudeクライアントのモック"""
        return AsyncMock()

    @pytest.fixture
    def mock_discord_client(self):
        """Discordクライアントのモック"""
        client = AsyncMock()
        client.set_message_handler = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_calendar_query_flow(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """カレンダー問い合わせフロー"""
        # Arrange
        mock_claude_client.chat_with_tools.return_value = (
            "かしこまりました。本日の予定は以下の通りでございます。\n"
            "- 10:00: ミーティング\n"
            "- 14:00: 病院予約"
        )

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        # Act
        response = await butler.handle_message("今日の予定を教えて", "予定")

        # Assert
        assert "かしこまりました" in response
        mock_claude_client.chat_with_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_weather_query_flow(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """天気問い合わせフロー"""
        # Arrange
        mock_claude_client.chat_with_tools.return_value = (
            "かしこまりました。本日の天気は晴れ、最高気温12度でございます。"
        )

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
            )

        # Act
        response = await butler.handle_message("今日の天気は？", "雑談")

        # Assert
        assert "天気" in response
