"""テスト共通フィクスチャ"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from src.clients.calendar import CalendarEvent
from src.clients.weather import WeatherInfo


# ========== 基本設定モック ==========


@pytest.fixture
def mock_settings():
    """設定のモック"""
    settings = MagicMock()
    settings.butler_name = "黒田"
    settings.discord_channel_schedule = "予定"
    settings.discord_channel_region = "地域のこと"
    settings.timezone = "Asia/Tokyo"
    settings.log_dir = None
    return settings


# ========== クライアントモック ==========


@pytest.fixture
def mock_calendar_client():
    """Google Calendarクライアントのモック"""
    client = AsyncMock()
    client.get_today_events = AsyncMock(return_value=[])
    client.get_week_events = AsyncMock(return_value=[])
    client.create_event = AsyncMock()
    return client


@pytest.fixture
def mock_claude_client():
    """Claudeクライアントのモック"""
    client = AsyncMock()
    client.filter_important_events = AsyncMock(return_value=[])
    client.generate_butler_message = AsyncMock(return_value="テストメッセージ")
    client.extract_events_from_search = AsyncMock(return_value=[])
    client.generate_event_recommendation = AsyncMock(return_value="週末のおすすめ")
    client.chat_with_tools = AsyncMock(return_value="応答メッセージ")
    return client


@pytest.fixture
def mock_discord_client():
    """Discordクライアントのモック"""
    client = AsyncMock()
    client.send_to_channel = AsyncMock(return_value=True)
    client.send_error_notification = AsyncMock(return_value=True)
    client.set_message_handler = MagicMock()
    client.is_duplicate_message = AsyncMock(return_value=False)
    return client


@pytest.fixture
def mock_weather_client():
    """天気クライアントのモック"""
    client = AsyncMock()
    client.get_today_weather = AsyncMock(return_value=None)
    client.get_weather_forecast = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_event_search_client():
    """イベント検索クライアントのモック"""
    client = AsyncMock()
    client.search_events = AsyncMock(return_value=[])
    client.format_reference_links = MagicMock(return_value="")
    client.build_events_from_results = MagicMock(return_value=[])
    client.build_reference_events = MagicMock(return_value=[])
    return client


@pytest.fixture
def mock_today_info_client():
    """今日は何の日クライアントのモック"""
    client = AsyncMock()
    client.get_today_info = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_life_info_client():
    """生活影響情報クライアントのモック"""
    client = AsyncMock()
    client.search_life_info = AsyncMock(return_value=[])
    client.get_all_life_info = AsyncMock(return_value=[])
    # format_for_weekly_notification は同期メソッド
    client.format_for_weekly_notification = MagicMock(return_value="")
    return client


@pytest.fixture
def mock_web_search_client():
    """Web検索クライアントのモック"""
    client = AsyncMock()
    client.search = AsyncMock(return_value="検索結果")
    return client


@pytest.fixture
def mock_reminder_client():
    """リマインダークライアントのモック"""
    client = MagicMock()
    client.set_reminder = MagicMock(return_value="reminder-001")
    client.list_reminders = MagicMock(return_value=[])
    client.delete_reminder = MagicMock(return_value=True)
    return client


@pytest.fixture
def mock_shopping_list_client():
    """買い物リストクライアントのモック"""
    client = MagicMock()
    client.add_item = MagicMock(return_value="item-001")
    client.list_items = MagicMock(return_value=[])
    client.remove_item = MagicMock(return_value=True)
    return client


@pytest.fixture
def mock_housework_client():
    """家事記録クライアントのモック"""
    client = MagicMock()
    client.add_task = MagicMock(return_value="task-001")
    client.mark_done = MagicMock(return_value=True)
    client.list_tasks = MagicMock(return_value=[])
    return client


@pytest.fixture
def mock_home_assistant_client():
    """Home Assistantクライアントのモック"""
    client = AsyncMock()
    client.control_light = AsyncMock(return_value=True)
    client.control_climate = AsyncMock(return_value=True)
    client.get_room_environment = AsyncMock(return_value={})
    return client


@pytest.fixture
def mock_expense_client():
    """家計簿クライアントのモック"""
    client = MagicMock()
    client.record_expense = MagicMock(return_value="expense-001")
    client.record_income = MagicMock(return_value="income-001")
    client.get_summary = MagicMock(return_value={})
    return client


@pytest.fixture
def mock_school_client():
    """学校情報クライアントのモック"""
    client = MagicMock()
    client.get_events = MagicMock(return_value=[])
    client.get_supplies = MagicMock(return_value=[])
    return client


@pytest.fixture
def mock_health_client():
    """健康記録クライアントのモック"""
    client = MagicMock()
    client.record_symptom = MagicMock(return_value="symptom-001")
    client.list_records = MagicMock(return_value=[])
    return client


# ========== サンプルデータ ==========


@pytest.fixture
def sample_events():
    """サンプルカレンダーイベント"""
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
        CalendarEvent(
            id="event-003",
            summary="保護者会",
            start=datetime(2026, 1, 24, 14, 0, tzinfo=tz),
            end=datetime(2026, 1, 24, 16, 0, tzinfo=tz),
            location="精華小学校",
        ),
    ]


@pytest.fixture
def sample_weather():
    """サンプル天気情報"""
    tz = ZoneInfo("Asia/Tokyo")
    return WeatherInfo(
        date=datetime(2026, 1, 24, tzinfo=tz),
        weather_code=1,
        weather_description="晴れ",
        temperature_max=12.0,
        temperature_min=3.0,
        precipitation_probability=10,
        precipitation_sum=0.0,
        sunrise="06:58",
        sunset="17:12",
    )


@pytest.fixture
def sample_search_results():
    """サンプル検索結果"""
    return [
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


# ========== パッチヘルパー ==========


@pytest.fixture
def patch_path_exists():
    """Path.existsをモックするコンテキストマネージャ"""
    with patch("src.butler.Path.exists", return_value=False):
        yield
