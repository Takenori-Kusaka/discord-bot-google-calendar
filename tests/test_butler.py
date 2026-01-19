"""Butler コアクラスのテスト"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from zoneinfo import ZoneInfo

from src.butler import Butler
from src.clients.calendar import CalendarEvent


@pytest.fixture
def mock_settings():
    """設定のモック"""
    settings = MagicMock()
    settings.butler_name = "黒田"
    settings.discord_channel_schedule = "予定"
    return settings


@pytest.fixture
def mock_calendar_client():
    """カレンダークライアントのモック"""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_claude_client():
    """Claudeクライアントのモック"""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_discord_client():
    """Discordクライアントのモック"""
    client = AsyncMock()
    client.send_to_channel = AsyncMock(return_value=True)
    client.send_error_notification = AsyncMock(return_value=True)
    return client


@pytest.fixture
def sample_events():
    """サンプルイベント"""
    tz = ZoneInfo("Asia/Tokyo")
    return [
        CalendarEvent(
            id="1",
            summary="病院予約",
            start=datetime(2026, 1, 15, 10, 0, tzinfo=tz),
            end=datetime(2026, 1, 15, 11, 0, tzinfo=tz),
            location="木津川市立病院",
        ),
        CalendarEvent(
            id="2",
            summary="仕事",
            start=datetime(2026, 1, 15, 9, 0, tzinfo=tz),
            end=datetime(2026, 1, 15, 18, 0, tzinfo=tz),
        ),
    ]


class TestButler:
    """Butlerクラスのテスト"""

    @pytest.mark.asyncio
    async def test_morning_notification_success(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
        sample_events,
    ):
        """朝の通知が正常に送信される"""
        # Arrange
        mock_calendar_client.get_today_events.return_value = sample_events
        mock_claude_client.filter_important_events.return_value = [sample_events[0]]
        mock_claude_client.generate_butler_message.return_value = "テストメッセージ"

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
        mock_calendar_client.get_today_events.assert_called_once()
        mock_claude_client.filter_important_events.assert_called_once()
        mock_claude_client.generate_butler_message.assert_called_once()
        mock_discord_client.send_to_channel.assert_called_once_with(
            "予定", "テストメッセージ"
        )

    @pytest.mark.asyncio
    async def test_morning_notification_no_events(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """予定がない場合も通知される"""
        # Arrange
        mock_calendar_client.get_today_events.return_value = []
        mock_claude_client.filter_important_events.return_value = []
        mock_claude_client.generate_butler_message.return_value = (
            "本日のご予定はございません"
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
        mock_discord_client.send_to_channel.assert_called_once()

    @pytest.mark.asyncio
    async def test_morning_notification_error_handling(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """エラー時にDM通知が送信される"""
        # Arrange
        mock_calendar_client.get_today_events.side_effect = Exception("API Error")

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
    async def test_weekly_event_notification_success(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """週次イベント通知が正常に送信される"""
        # Arrange
        mock_settings.discord_channel_region = "地域のこと"
        mock_event_search = AsyncMock()
        mock_event_search.search_events.return_value = [
            {"title": "高の原イベント", "snippet": "テスト"}
        ]
        # format_reference_linksは同期メソッドなのでMagicMock()を使用
        mock_event_search.format_reference_links = MagicMock(return_value="")
        mock_claude_client.extract_events_from_search.return_value = [
            {"title": "お祭り", "date": "1/18(土)", "location": "高の原"}
        ]
        mock_claude_client.generate_event_recommendation.return_value = "週末のおすすめ"

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                event_search_client=mock_event_search,
            )

        # Act
        await butler.weekly_event_notification()

        # Assert
        mock_event_search.search_events.assert_called_once()
        mock_claude_client.extract_events_from_search.assert_called_once()
        mock_claude_client.generate_event_recommendation.assert_called_once()
        mock_discord_client.send_to_channel.assert_called_once_with(
            "地域のこと", "週末のおすすめ"
        )

    @pytest.mark.asyncio
    async def test_weekly_event_notification_no_client(
        self,
        mock_settings,
        mock_calendar_client,
        mock_claude_client,
        mock_discord_client,
    ):
        """イベント検索クライアントがない場合は何もしない"""
        # Arrange
        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=mock_settings,
                calendar_client=mock_calendar_client,
                claude_client=mock_claude_client,
                discord_client=mock_discord_client,
                event_search_client=None,
            )

        # Act
        await butler.weekly_event_notification()

        # Assert
        mock_discord_client.send_to_channel.assert_not_called()
