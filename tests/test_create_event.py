"""
Tests for create_event.py
"""

import datetime
import os
import sys
from unittest.mock import MagicMock, AsyncMock
import pytest
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from create_event import get_calendar_service, fetch_events, is_same_event  # noqa: E402

# .env ファイルを読み込む
load_dotenv()

class MockDiscordEvent:
    """Mock Discord scheduled event class for testing"""
    def __init__(self, name: str, start_time: datetime.datetime, end_time: datetime.datetime):
        self.name = name
        self.start_time = start_time
        self.end_time = end_time

@pytest.fixture
def mock_calendar_event():
    """カレンダーイベントのモックを作成"""
    return {
        'summary': 'Test Event',
        'start': {'dateTime': '2024-01-01T10:00:00+09:00'},
        'end': {'dateTime': '2024-01-01T11:00:00+09:00'},
        'description': 'Test Description',
        'location': 'Test Location'
    }

@pytest.fixture
def mock_discord_event():
    """Discordイベントのモックを作成"""
    tz_jst = datetime.timezone(datetime.timedelta(hours=9))
    start_time = datetime.datetime(2024, 1, 1, 10, 0, tzinfo=tz_jst)
    end_time = datetime.datetime(2024, 1, 1, 11, 0, tzinfo=tz_jst)
    return MockDiscordEvent('Test Event', start_time, end_time)

def test_get_calendar_service():
    """Test getting calendar service."""
    service = get_calendar_service()
    assert service is not None

def test_fetch_events():
    """Test fetching events from calendar."""
    service = get_calendar_service()
    start_date = datetime.date(2024, 1, 1)
    end_date = datetime.date(2024, 1, 31)
    events = fetch_events(service, start_date, end_date)
    assert isinstance(events, list)

def test_is_same_event_matching(mock_calendar_event, mock_discord_event):
    """同じイベントを正しく識別できることをテスト"""
    jst = datetime.timezone(datetime.timedelta(hours=9))
    start_time = datetime.datetime.fromisoformat(mock_calendar_event['start']['dateTime'])
    end_time = datetime.datetime.fromisoformat(mock_calendar_event['end']['dateTime'])
    
    assert is_same_event(mock_discord_event, mock_calendar_event, start_time, end_time)

def test_is_same_event_different_name(mock_calendar_event, mock_discord_event):
    """名前が異なる場合は別イベントと識別されることをテスト"""
    jst = datetime.timezone(datetime.timedelta(hours=9))
    start_time = datetime.datetime.fromisoformat(mock_calendar_event['start']['dateTime'])
    end_time = datetime.datetime.fromisoformat(mock_calendar_event['end']['dateTime'])
    
    mock_discord_event.name = "Different Event"
    assert not is_same_event(mock_discord_event, mock_calendar_event, start_time, end_time)

def test_is_same_event_different_date(mock_calendar_event, mock_discord_event):
    """日付が異なる場合は別イベントと識別されることをテスト"""
    jst = datetime.timezone(datetime.timedelta(hours=9))
    # カレンダーイベントの日付を1日ずらす
    start_time = datetime.datetime.fromisoformat(mock_calendar_event['start']['dateTime']) + datetime.timedelta(days=1)
    end_time = datetime.datetime.fromisoformat(mock_calendar_event['end']['dateTime']) + datetime.timedelta(days=1)
    
    assert not is_same_event(mock_discord_event, mock_calendar_event, start_time, end_time)

@pytest.mark.asyncio
async def test_create_discord_events():
    """Discordイベント作成機能の統合テスト"""
    from create_event import create_discord_events
    
    # モックの設定
    mock_guild = MagicMock()
    mock_guild.fetch_scheduled_events = AsyncMock(return_value=[])
    mock_guild.create_scheduled_event = AsyncMock()
    
    mock_service = MagicMock()
    mock_service.events().list().execute.return_value = {
        'items': [{
            'summary': 'Test Event',
            'start': {'dateTime': '2024-01-01T10:00:00+09:00'},
            'end': {'dateTime': '2024-01-01T11:00:00+09:00'},
            'description': 'Test Description',
            'location': 'Test Location'
        }]
    }
    
    # テスト実行
    created_count = await create_discord_events(mock_guild, mock_service)
    
    # 検証
    assert created_count == 1
    mock_guild.create_scheduled_event.assert_called_once()

@pytest.mark.asyncio
async def test_create_discord_events_success():
    """Discordイベント作成の成功ケースをテスト"""
    from create_event import create_discord_events
    guild = MagicMock()
    guild.fetch_scheduled_events = AsyncMock(return_value=[])
    guild.create_scheduled_event = AsyncMock()
    
    service = MagicMock()
    mock_events = {
        'items': [{
            'summary': 'Test Event',
            'start': {'dateTime': '2024-01-01T10:00:00+09:00'},
            'end': {'dateTime': '2024-01-01T11:00:00+09:00'},
            'description': 'Test Description',
            'location': 'Test Location'
        }]
    }
    service.events().list().execute.return_value = mock_events
    
    created_count = await create_discord_events(guild, service)
    assert created_count == 1
    guild.create_scheduled_event.assert_called_once()
