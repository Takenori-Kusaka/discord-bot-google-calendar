"""エージェントツール定義と実行"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ツール定義スキーマ
TOOL_DEFINITIONS = [
    {
        "name": "get_calendar_events",
        "description": "Googleカレンダーから予定を取得します。今日、明日、今週などの予定を確認できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_range": {
                    "type": "string",
                    "enum": ["today", "tomorrow", "this_week", "next_week"],
                    "description": "取得する期間",
                }
            },
            "required": ["date_range"],
        },
    },
    {
        "name": "get_weather",
        "description": "木津川市の天気予報を取得します。今日の天気や週間予報を確認できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "何日分の予報を取得するか（1-7）",
                    "default": 1,
                }
            },
        },
    },
    {
        "name": "search_events",
        "description": "木津川市・奈良市周辺の地域イベントを検索します。家族向けのイベントを探せます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "検索キーワード（例: 子供向け、週末、無料）",
                }
            },
        },
    },
    {
        "name": "get_life_info",
        "description": "家族に関連する法改正や制度変更などの生活影響情報を取得します。児童手当、保育、税金などの情報が確認できます。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_today_info",
        "description": "今日が何の日かを取得します。記念日や豆知識を提供します。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_family_info",
        "description": "家族情報（ゴミ出し日、よく行く場所など）を参照します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["garbage", "favorite_places", "all"],
                    "description": "取得する情報カテゴリ",
                }
            },
            "required": ["category"],
        },
    },
]


@dataclass
class ToolResult:
    """ツール実行結果"""

    tool_use_id: str
    content: str
    is_error: bool = False


class ToolExecutor:
    """ツール実行器"""

    def __init__(
        self,
        calendar_client=None,
        weather_client=None,
        event_search_client=None,
        life_info_client=None,
        today_info_client=None,
        family_data: Optional[dict] = None,
        timezone: str = "Asia/Tokyo",
    ):
        """初期化

        Args:
            calendar_client: Google Calendarクライアント
            weather_client: 天気クライアント
            event_search_client: イベント検索クライアント
            life_info_client: 生活影響情報クライアント
            today_info_client: 今日は何の日クライアント
            family_data: 家族情報
            timezone: タイムゾーン
        """
        self.calendar_client = calendar_client
        self.weather_client = weather_client
        self.event_search_client = event_search_client
        self.life_info_client = life_info_client
        self.today_info_client = today_info_client
        self.family_data = family_data or {}
        self.timezone = timezone

        # ツールハンドラマッピング
        self._handlers: dict[str, Callable] = {
            "get_calendar_events": self._get_calendar_events,
            "get_weather": self._get_weather,
            "search_events": self._search_events,
            "get_life_info": self._get_life_info,
            "get_today_info": self._get_today_info,
            "get_family_info": self._get_family_info,
        }

        logger.info("Tool executor initialized")

    async def execute(self, tool_name: str, tool_input: dict, tool_use_id: str) -> ToolResult:
        """ツールを実行

        Args:
            tool_name: ツール名
            tool_input: ツール入力
            tool_use_id: ツール使用ID

        Returns:
            ToolResult: 実行結果
        """
        logger.info(f"Executing tool: {tool_name}", input=tool_input)

        if tool_name not in self._handlers:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error: Unknown tool '{tool_name}'",
                is_error=True,
            )

        try:
            result = await self._handlers[tool_name](tool_input)
            logger.info(f"Tool {tool_name} completed", result_length=len(result))
            return ToolResult(tool_use_id=tool_use_id, content=result)
        except Exception as e:
            logger.error(f"Tool {tool_name} failed", error=str(e))
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error executing {tool_name}: {str(e)}",
                is_error=True,
            )

    async def _get_calendar_events(self, tool_input: dict) -> str:
        """カレンダー予定を取得"""
        if not self.calendar_client:
            return "カレンダークライアントが設定されていません。"

        date_range = tool_input.get("date_range", "today")
        now = datetime.now(ZoneInfo(self.timezone))

        if date_range == "today":
            events = await self.calendar_client.get_today_events()
        elif date_range == "tomorrow":
            events = await self.calendar_client.get_events_for_date(
                now + timedelta(days=1)
            )
        elif date_range == "this_week":
            events = await self.calendar_client.get_week_events()
        elif date_range == "next_week":
            # 来週の予定（簡易実装）
            events = await self.calendar_client.get_week_events()
        else:
            events = await self.calendar_client.get_today_events()

        if not events:
            return f"{date_range}の予定はございません。"

        lines = [f"【{date_range}の予定】"]
        for event in events:
            time_str = event.start.strftime("%H:%M") if not event.all_day else "終日"
            lines.append(f"- {time_str}: {event.summary}")

        return "\n".join(lines)

    async def _get_weather(self, tool_input: dict) -> str:
        """天気予報を取得"""
        if not self.weather_client:
            return "天気クライアントが設定されていません。"

        days = tool_input.get("days", 1)

        if days == 1:
            weather = await self.weather_client.get_today_weather()
            if not weather:
                return "天気情報を取得できませんでした。"
            return f"【本日の天気】\n{weather.format_for_notification()}"
        else:
            forecasts = await self.weather_client.get_weather_forecast(days=days)
            if not forecasts:
                return "天気予報を取得できませんでした。"

            lines = [f"【{days}日間の天気予報】"]
            for forecast in forecasts:
                date_str = forecast.date.strftime("%m/%d(%a)")
                lines.append(
                    f"- {date_str}: {forecast.weather_description} "
                    f"({forecast.temperature_min:.0f}°C〜{forecast.temperature_max:.0f}°C)"
                )

            return "\n".join(lines)

    async def _search_events(self, tool_input: dict) -> str:
        """地域イベントを検索"""
        if not self.event_search_client:
            return "イベント検索クライアントが設定されていません。"

        query = tool_input.get("query", "")

        # イベント検索を実行
        search_results = await self.event_search_client.search_events()

        if not search_results:
            return "イベント情報を取得できませんでした。"

        # クエリでフィルタリング（簡易実装）
        if query:
            filtered = [r for r in search_results if query in str(r)]
            if filtered:
                search_results = filtered

        lines = ["【地域イベント情報】"]
        for result in search_results[:5]:  # 最大5件
            lines.append(f"- {result.get('title', '不明')}")
            if result.get("date"):
                lines.append(f"  日時: {result.get('date')}")
            if result.get("location"):
                lines.append(f"  場所: {result.get('location')}")

        return "\n".join(lines)

    async def _get_life_info(self, tool_input: dict) -> str:
        """生活影響情報を取得"""
        if not self.life_info_client:
            return "生活影響情報クライアントが設定されていません。"

        info_list = await self.life_info_client.get_all_life_info()

        if not info_list:
            return "現在、特筆すべき生活影響情報はございません。"

        return self.life_info_client.format_for_weekly_notification(info_list[:5])

    async def _get_today_info(self, tool_input: dict) -> str:
        """今日は何の日を取得"""
        if not self.today_info_client:
            return "今日は何の日クライアントが設定されていません。"

        info = await self.today_info_client.get_today_info()

        if not info:
            return "今日は何の日情報を取得できませんでした。"

        return f"【今日は何の日】\n{info.format_for_notification()}"

    async def _get_family_info(self, tool_input: dict) -> str:
        """家族情報を取得"""
        category = tool_input.get("category", "all")

        if not self.family_data:
            return "家族情報が設定されていません。"

        if category == "garbage":
            garbage = self.family_data.get("garbage", {})
            if not garbage:
                return "ごみ出し情報は設定されていません。"

            lines = ["【ごみ出しスケジュール】"]
            for schedule in garbage.get("schedule", []):
                lines.append(
                    f"- {schedule.get('type', '')}: {schedule.get('days', schedule.get('frequency', ''))}"
                )
            return "\n".join(lines)

        elif category == "favorite_places":
            location = self.family_data.get("location", {})
            places = location.get("favorite_places", [])
            if not places:
                return "お気に入りの場所は設定されていません。"

            lines = ["【よく行く場所】"]
            for place in places:
                lines.append(f"- {place.get('name', '')}: {place.get('type', '')}")
            return "\n".join(lines)

        else:  # all
            lines = []

            # ごみ出し
            garbage = self.family_data.get("garbage", {})
            if garbage:
                lines.append("【ごみ出しスケジュール】")
                for schedule in garbage.get("schedule", []):
                    lines.append(
                        f"- {schedule.get('type', '')}: {schedule.get('days', schedule.get('frequency', ''))}"
                    )

            # お気に入りの場所
            location = self.family_data.get("location", {})
            places = location.get("favorite_places", [])
            if places:
                lines.append("\n【よく行く場所】")
                for place in places:
                    lines.append(f"- {place.get('name', '')}: {place.get('type', '')}")

            return "\n".join(lines) if lines else "家族情報が設定されていません。"


def get_tool_definitions() -> list[dict]:
    """ツール定義を取得"""
    return TOOL_DEFINITIONS
