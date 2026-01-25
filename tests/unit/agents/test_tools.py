"""ToolExecutor の単体テスト"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from src.agents.tools import ToolExecutor, ToolResult, TOOL_DEFINITIONS, get_tool_definitions
from src.clients.calendar import CalendarEvent
from src.clients.weather import WeatherInfo


class TestToolDefinitions:
    """ツール定義のテスト"""

    def test_tool_definitions_exist(self):
        """ツール定義が存在する"""
        assert len(TOOL_DEFINITIONS) > 0

    def test_all_tools_have_required_fields(self):
        """全ツールが必須フィールドを持つ"""
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_get_tool_definitions(self):
        """get_tool_definitions関数のテスト"""
        tools = get_tool_definitions()
        assert tools == TOOL_DEFINITIONS

    def test_calendar_tool_definition(self):
        """カレンダーツール定義"""
        calendar_tool = next(
            (t for t in TOOL_DEFINITIONS if t["name"] == "get_calendar_events"), None
        )
        assert calendar_tool is not None
        assert "date_range" in calendar_tool["input_schema"]["properties"]

    def test_weather_tool_definition(self):
        """天気ツール定義"""
        weather_tool = next(
            (t for t in TOOL_DEFINITIONS if t["name"] == "get_weather"), None
        )
        assert weather_tool is not None
        assert "days" in weather_tool["input_schema"]["properties"]

    def test_create_event_tool_definition(self):
        """予定作成ツール定義"""
        create_tool = next(
            (t for t in TOOL_DEFINITIONS if t["name"] == "create_calendar_event"), None
        )
        assert create_tool is not None
        assert "summary" in create_tool["input_schema"]["properties"]
        assert "date" in create_tool["input_schema"]["properties"]


class TestToolResult:
    """ToolResultクラスのテスト"""

    def test_tool_result_creation(self):
        """ToolResultの作成"""
        result = ToolResult(
            tool_use_id="test-001",
            content="テスト結果",
            is_error=False,
        )
        assert result.tool_use_id == "test-001"
        assert result.content == "テスト結果"
        assert result.is_error is False

    def test_tool_result_error(self):
        """エラー結果の作成"""
        result = ToolResult(
            tool_use_id="test-002",
            content="エラーメッセージ",
            is_error=True,
        )
        assert result.is_error is True


class TestToolExecutor:
    """ToolExecutorクラスのテスト"""

    @pytest.fixture
    def mock_calendar_client(self):
        """カレンダークライアントのモック"""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_weather_client(self):
        """天気クライアントのモック"""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_event_search_client(self):
        """イベント検索クライアントのモック"""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_reminder_client(self):
        """リマインダークライアントのモック"""
        client = MagicMock()
        return client

    @pytest.fixture
    def mock_shopping_list_client(self):
        """買い物リストクライアントのモック"""
        client = MagicMock()
        return client

    @pytest.fixture
    def mock_housework_client(self):
        """家事クライアントのモック"""
        client = MagicMock()
        return client

    @pytest.fixture
    def mock_home_assistant_client(self):
        """Home Assistantクライアントのモック"""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_expense_client(self):
        """家計簿クライアントのモック"""
        client = MagicMock()
        return client

    @pytest.fixture
    def sample_family_data(self):
        """サンプル家族データ"""
        return {
            "garbage": {
                "schedule": [
                    {"type": "燃えるごみ", "days": "月・木"},
                    {"type": "プラスチック", "days": "火"},
                ]
            },
            "location": {
                "favorite_places": [
                    {"name": "イオンモール高の原", "type": "ショッピング"},
                    {"name": "木津川市立図書館", "type": "公共施設"},
                ]
            },
        }

    @pytest.fixture
    def tool_executor(
        self,
        mock_calendar_client,
        mock_weather_client,
        mock_event_search_client,
        mock_reminder_client,
        mock_shopping_list_client,
        mock_housework_client,
        mock_home_assistant_client,
        mock_expense_client,
        sample_family_data,
    ):
        """ToolExecutorのインスタンス"""
        return ToolExecutor(
            calendar_client=mock_calendar_client,
            weather_client=mock_weather_client,
            event_search_client=mock_event_search_client,
            reminder_client=mock_reminder_client,
            shopping_list_client=mock_shopping_list_client,
            housework_client=mock_housework_client,
            home_assistant_client=mock_home_assistant_client,
            expense_client=mock_expense_client,
            family_data=sample_family_data,
            timezone="Asia/Tokyo",
        )


class TestGetCalendarEvents(TestToolExecutor):
    """get_calendar_eventsツールのテスト"""

    @pytest.mark.asyncio
    async def test_get_today_events(self, tool_executor, mock_calendar_client):
        """今日の予定を取得"""
        tz = ZoneInfo("Asia/Tokyo")
        mock_calendar_client.get_today_events.return_value = [
            CalendarEvent(
                id="event-001",
                summary="ミーティング",
                start=datetime(2026, 1, 24, 10, 0, tzinfo=tz),
                end=datetime(2026, 1, 24, 11, 0, tzinfo=tz),
            )
        ]

        result = await tool_executor.execute(
            "get_calendar_events",
            {"date_range": "today"},
            "tool-001",
        )

        assert result.is_error is False
        assert "ミーティング" in result.content
        assert "10:00" in result.content

    @pytest.mark.asyncio
    async def test_get_events_empty(self, tool_executor, mock_calendar_client):
        """予定がない場合"""
        mock_calendar_client.get_today_events.return_value = []

        result = await tool_executor.execute(
            "get_calendar_events",
            {"date_range": "today"},
            "tool-002",
        )

        assert result.is_error is False
        assert "ございません" in result.content

    @pytest.mark.asyncio
    async def test_get_events_no_client(self):
        """クライアントがない場合"""
        executor = ToolExecutor()

        result = await executor.execute(
            "get_calendar_events",
            {"date_range": "today"},
            "tool-003",
        )

        assert "設定されていません" in result.content


class TestGetWeather(TestToolExecutor):
    """get_weatherツールのテスト"""

    @pytest.mark.asyncio
    async def test_get_today_weather(self, tool_executor, mock_weather_client):
        """今日の天気を取得"""
        tz = ZoneInfo("Asia/Tokyo")
        mock_weather_client.get_today_weather.return_value = WeatherInfo(
            date=datetime(2026, 1, 24, tzinfo=tz),
            weather_code=1,
            weather_description="晴れ",
            temperature_max=12.0,
            temperature_min=3.0,
            precipitation_probability=10,
            precipitation_sum=0.0,
        )

        result = await tool_executor.execute(
            "get_weather",
            {"days": 1},
            "tool-001",
        )

        assert result.is_error is False
        assert "晴れ" in result.content

    @pytest.mark.asyncio
    async def test_get_weather_forecast(self, tool_executor, mock_weather_client):
        """週間予報を取得"""
        tz = ZoneInfo("Asia/Tokyo")
        mock_weather_client.get_weather_forecast.return_value = [
            WeatherInfo(
                date=datetime(2026, 1, 24, tzinfo=tz),
                weather_code=1,
                weather_description="晴れ",
                temperature_max=12.0,
                temperature_min=3.0,
                precipitation_probability=10,
                precipitation_sum=0.0,
            ),
            WeatherInfo(
                date=datetime(2026, 1, 25, tzinfo=tz),
                weather_code=3,
                weather_description="曇り",
                temperature_max=10.0,
                temperature_min=4.0,
                precipitation_probability=30,
                precipitation_sum=0.0,
            ),
        ]

        result = await tool_executor.execute(
            "get_weather",
            {"days": 3},
            "tool-002",
        )

        assert result.is_error is False
        assert "晴れ" in result.content
        assert "曇り" in result.content

    @pytest.mark.asyncio
    async def test_get_weather_no_client(self):
        """クライアントがない場合"""
        executor = ToolExecutor()

        result = await executor.execute(
            "get_weather",
            {"days": 1},
            "tool-003",
        )

        assert "設定されていません" in result.content


class TestGetFamilyInfo(TestToolExecutor):
    """get_family_infoツールのテスト"""

    @pytest.mark.asyncio
    async def test_get_garbage_info(self, tool_executor):
        """ごみ出し情報を取得"""
        result = await tool_executor.execute(
            "get_family_info",
            {"category": "garbage"},
            "tool-001",
        )

        assert result.is_error is False
        assert "燃えるごみ" in result.content
        assert "月・木" in result.content

    @pytest.mark.asyncio
    async def test_get_favorite_places(self, tool_executor):
        """お気に入りの場所を取得"""
        result = await tool_executor.execute(
            "get_family_info",
            {"category": "favorite_places"},
            "tool-002",
        )

        assert result.is_error is False
        assert "イオンモール高の原" in result.content

    @pytest.mark.asyncio
    async def test_get_all_family_info(self, tool_executor):
        """全家族情報を取得"""
        result = await tool_executor.execute(
            "get_family_info",
            {"category": "all"},
            "tool-003",
        )

        assert result.is_error is False
        assert "ごみ出し" in result.content
        assert "よく行く場所" in result.content

    @pytest.mark.asyncio
    async def test_get_family_info_no_data(self):
        """家族データがない場合"""
        executor = ToolExecutor()

        result = await executor.execute(
            "get_family_info",
            {"category": "garbage"},
            "tool-004",
        )

        assert "設定されていません" in result.content


class TestUnknownTool(TestToolExecutor):
    """未知のツールのテスト"""

    @pytest.mark.asyncio
    async def test_unknown_tool(self, tool_executor):
        """未知のツールを呼び出した場合"""
        result = await tool_executor.execute(
            "unknown_tool",
            {},
            "tool-001",
        )

        assert result.is_error is True
        assert "Unknown tool" in result.content


class TestToolError(TestToolExecutor):
    """ツールエラーのテスト"""

    @pytest.mark.asyncio
    async def test_tool_execution_error(self, tool_executor, mock_calendar_client):
        """ツール実行中にエラーが発生した場合"""
        mock_calendar_client.get_today_events.side_effect = Exception("API Error")

        result = await tool_executor.execute(
            "get_calendar_events",
            {"date_range": "today"},
            "tool-001",
        )

        assert result.is_error is True
        assert "Error" in result.content


class TestShoppingList(TestToolExecutor):
    """買い物リストツールのテスト"""

    @pytest.mark.asyncio
    async def test_add_shopping_item(self, tool_executor, mock_shopping_list_client):
        """買い物アイテムを追加"""
        mock_shopping_list_client.add_item.return_value = "item-001"

        result = await tool_executor.execute(
            "add_shopping_item",
            {"name": "牛乳", "quantity": "2本"},
            "tool-001",
        )

        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_list_shopping(self, tool_executor, mock_shopping_list_client):
        """買い物リストを表示"""
        mock_shopping_list_client.list_items.return_value = [
            {"id": "item-001", "name": "牛乳", "quantity": "2本"},
        ]

        result = await tool_executor.execute(
            "list_shopping",
            {},
            "tool-002",
        )

        assert result.is_error is False


class TestReminder(TestToolExecutor):
    """リマインダーツールのテスト"""

    @pytest.mark.asyncio
    async def test_set_reminder(self, tool_executor, mock_reminder_client):
        """リマインダーを設定"""
        mock_reminder_client.set_reminder.return_value = "reminder-001"

        result = await tool_executor.execute(
            "set_reminder",
            {"message": "電話する", "date": "2026-01-25", "time": "10:00"},
            "tool-001",
        )

        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_list_reminders(self, tool_executor, mock_reminder_client):
        """リマインダー一覧を取得"""
        mock_reminder_client.list_reminders.return_value = [
            {"id": "reminder-001", "message": "電話する", "datetime": "2026-01-25 10:00"},
        ]

        result = await tool_executor.execute(
            "list_reminders",
            {},
            "tool-002",
        )

        assert result.is_error is False


class TestHomeAssistant(TestToolExecutor):
    """Home Assistantツールのテスト"""

    @pytest.mark.asyncio
    async def test_control_light(self, tool_executor, mock_home_assistant_client):
        """照明を制御"""
        mock_home_assistant_client.control_light.return_value = True

        result = await tool_executor.execute(
            "control_light",
            {"room": "書斎", "action": "on"},
            "tool-001",
        )

        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_control_climate(self, tool_executor, mock_home_assistant_client):
        """エアコンを制御"""
        mock_home_assistant_client.control_climate.return_value = True

        result = await tool_executor.execute(
            "control_climate",
            {"room": "リビング", "action": "on", "temperature": 22},
            "tool-002",
        )

        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_get_room_environment(self, tool_executor, mock_home_assistant_client):
        """室内環境を取得"""
        mock_home_assistant_client.get_room_environment.return_value = {
            "temperature": 22.5,
            "humidity": 45,
        }

        result = await tool_executor.execute(
            "get_room_environment",
            {"room": "書斎"},
            "tool-003",
        )

        assert result.is_error is False


class TestExpense(TestToolExecutor):
    """家計簿ツールのテスト"""

    @pytest.mark.asyncio
    async def test_record_expense(self, tool_executor, mock_expense_client):
        """支出を記録"""
        mock_expense_client.record_expense.return_value = "expense-001"

        result = await tool_executor.execute(
            "record_expense",
            {"amount": 1000, "description": "スーパーで食材"},
            "tool-001",
        )

        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_record_income(self, tool_executor, mock_expense_client):
        """収入を記録"""
        mock_expense_client.record_income.return_value = "income-001"

        result = await tool_executor.execute(
            "record_income",
            {"amount": 300000, "description": "給与"},
            "tool-002",
        )

        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_get_expense_summary(self, tool_executor, mock_expense_client):
        """家計簿サマリーを取得"""
        mock_expense_client.get_summary.return_value = {
            "income": 300000,
            "expense": 150000,
            "balance": 150000,
        }

        result = await tool_executor.execute(
            "get_expense_summary",
            {"year": 2026, "month": 1},
            "tool-003",
        )

        assert result.is_error is False
