"""Google Calendar クライアントの単体テスト"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from zoneinfo import ZoneInfo

from src.clients.calendar import GoogleCalendarClient, CalendarEvent


class TestCalendarEvent:
    """CalendarEventクラスのテスト"""

    def test_calendar_event_creation(self):
        """CalendarEventの作成"""
        tz = ZoneInfo("Asia/Tokyo")
        event = CalendarEvent(
            id="test-001",
            summary="テスト予定",
            start=datetime(2026, 1, 24, 10, 0, tzinfo=tz),
            end=datetime(2026, 1, 24, 11, 0, tzinfo=tz),
            description="テスト説明",
            location="テスト場所",
            all_day=False,
        )

        assert event.id == "test-001"
        assert event.summary == "テスト予定"
        assert event.description == "テスト説明"
        assert event.location == "テスト場所"
        assert event.all_day is False

    def test_calendar_event_to_dict(self):
        """to_dictメソッドのテスト"""
        tz = ZoneInfo("Asia/Tokyo")
        event = CalendarEvent(
            id="test-001",
            summary="テスト予定",
            start=datetime(2026, 1, 24, 10, 0, tzinfo=tz),
            end=datetime(2026, 1, 24, 11, 0, tzinfo=tz),
        )

        result = event.to_dict()

        assert result["id"] == "test-001"
        assert result["summary"] == "テスト予定"
        assert "2026-01-24T10:00:00" in result["start"]
        assert result["all_day"] is False

    def test_calendar_event_repr(self):
        """__repr__メソッドのテスト"""
        tz = ZoneInfo("Asia/Tokyo")
        event = CalendarEvent(
            id="test-001",
            summary="テスト予定",
            start=datetime(2026, 1, 24, 10, 0, tzinfo=tz),
            end=datetime(2026, 1, 24, 11, 0, tzinfo=tz),
        )

        repr_str = repr(event)
        assert "テスト予定" in repr_str
        assert "CalendarEvent" in repr_str


class TestGoogleCalendarClient:
    """GoogleCalendarClientクラスのテスト"""

    @pytest.fixture
    def mock_service(self):
        """Google Calendar API サービスのモック"""
        service = MagicMock()
        service.events.return_value.list.return_value.execute.return_value = {
            "items": []
        }
        service.events.return_value.insert.return_value.execute.return_value = {
            "id": "new-event-001",
            "summary": "新規予定",
            "start": {"dateTime": "2026-01-24T10:00:00+09:00"},
            "end": {"dateTime": "2026-01-24T11:00:00+09:00"},
        }
        return service

    @pytest.fixture
    def calendar_client(self, mock_service):
        """GoogleCalendarClientのインスタンス（モック済み）"""
        with patch(
            "src.clients.calendar.service_account.Credentials.from_service_account_file"
        ) as mock_creds, patch("src.clients.calendar.build") as mock_build:
            mock_build.return_value = mock_service
            client = GoogleCalendarClient(
                calendar_id="test-calendar@example.com",
                credentials_path="fake/path/to/credentials.json",
                timezone="Asia/Tokyo",
            )
            return client

    @pytest.mark.asyncio
    async def test_get_today_events_empty(self, calendar_client, mock_service):
        """今日の予定が空の場合"""
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": []
        }

        events = await calendar_client.get_today_events()

        assert events == []
        mock_service.events.return_value.list.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_today_events_with_events(self, calendar_client, mock_service):
        """今日の予定がある場合"""
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "event-001",
                    "summary": "ミーティング",
                    "start": {"dateTime": "2026-01-24T10:00:00+09:00"},
                    "end": {"dateTime": "2026-01-24T11:00:00+09:00"},
                    "location": "会議室A",
                },
                {
                    "id": "event-002",
                    "summary": "終日予定",
                    "start": {"date": "2026-01-24"},
                    "end": {"date": "2026-01-25"},
                },
            ]
        }

        events = await calendar_client.get_today_events()

        assert len(events) == 2
        assert events[0].summary == "ミーティング"
        assert events[0].location == "会議室A"
        assert events[0].all_day is False
        assert events[1].summary == "終日予定"
        assert events[1].all_day is True

    @pytest.mark.asyncio
    async def test_get_week_events(self, calendar_client, mock_service):
        """今週の予定を取得"""
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "event-001",
                    "summary": "週間予定",
                    "start": {"dateTime": "2026-01-25T14:00:00+09:00"},
                    "end": {"dateTime": "2026-01-25T15:00:00+09:00"},
                }
            ]
        }

        events = await calendar_client.get_week_events()

        assert len(events) == 1
        assert events[0].summary == "週間予定"

    @pytest.mark.asyncio
    async def test_create_event_with_time(self, calendar_client, mock_service):
        """時間指定の予定を作成"""
        tz = ZoneInfo("Asia/Tokyo")
        start = datetime(2026, 1, 24, 10, 0, tzinfo=tz)
        end = datetime(2026, 1, 24, 11, 0, tzinfo=tz)

        event = await calendar_client.create_event(
            summary="新規予定",
            start=start,
            end=end,
            description="テスト説明",
            location="テスト場所",
        )

        assert event.id == "new-event-001"
        mock_service.events.return_value.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_event_all_day(self, calendar_client, mock_service):
        """終日予定を作成"""
        mock_service.events.return_value.insert.return_value.execute.return_value = {
            "id": "new-event-002",
            "summary": "終日予定",
            "start": {"date": "2026-01-24"},
            "end": {"date": "2026-01-25"},
        }

        tz = ZoneInfo("Asia/Tokyo")
        start = datetime(2026, 1, 24, 0, 0, tzinfo=tz)

        event = await calendar_client.create_event(
            summary="終日予定",
            start=start,
            all_day=True,
        )

        assert event.id == "new-event-002"
        mock_service.events.return_value.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_events_api_error(self, calendar_client, mock_service):
        """API エラー時の例外処理"""
        mock_service.events.return_value.list.return_value.execute.side_effect = (
            Exception("API Error")
        )

        with pytest.raises(Exception, match="API Error"):
            await calendar_client.get_today_events()

    @pytest.mark.asyncio
    async def test_create_event_api_error(self, calendar_client, mock_service):
        """予定作成時のAPIエラー"""
        mock_service.events.return_value.insert.return_value.execute.side_effect = (
            Exception("Create Error")
        )

        tz = ZoneInfo("Asia/Tokyo")
        start = datetime(2026, 1, 24, 10, 0, tzinfo=tz)

        with pytest.raises(Exception, match="Create Error"):
            await calendar_client.create_event(
                summary="エラー予定",
                start=start,
            )

    @pytest.mark.asyncio
    async def test_get_events_for_date(self, calendar_client, mock_service):
        """指定日の予定を取得"""
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "event-001",
                    "summary": "指定日予定",
                    "start": {"dateTime": "2026-01-25T10:00:00+09:00"},
                    "end": {"dateTime": "2026-01-25T11:00:00+09:00"},
                }
            ]
        }

        tz = ZoneInfo("Asia/Tokyo")
        date = datetime(2026, 1, 25, tzinfo=tz)

        events = await calendar_client.get_events_for_date(date)

        assert len(events) == 1
        assert events[0].summary == "指定日予定"

    def test_parse_event_without_title(self, calendar_client):
        """タイトルなしのイベントをパース"""
        event_data = {
            "id": "no-title-001",
            "start": {"dateTime": "2026-01-24T10:00:00+09:00"},
            "end": {"dateTime": "2026-01-24T11:00:00+09:00"},
        }

        event = calendar_client._parse_event(event_data)

        assert event.summary == "（タイトルなし）"
