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
    {
        "name": "create_calendar_event",
        "description": "Googleカレンダーに新しい予定を登録します。日時、タイトル、場所などを指定できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "予定のタイトル",
                },
                "date": {
                    "type": "string",
                    "description": "予定の日付（YYYY-MM-DD形式、例: 2026-01-25）",
                },
                "start_time": {
                    "type": "string",
                    "description": "開始時刻（HH:MM形式、例: 14:30）。省略時は終日予定になります。",
                },
                "end_time": {
                    "type": "string",
                    "description": "終了時刻（HH:MM形式、例: 15:30）。省略時は開始から1時間後になります。",
                },
                "description": {
                    "type": "string",
                    "description": "予定の説明（任意）",
                },
                "location": {
                    "type": "string",
                    "description": "場所（任意）",
                },
            },
            "required": ["summary", "date"],
        },
    },
    {
        "name": "web_search",
        "description": "インターネットで情報を検索します。最新のニュース、店舗情報、営業時間、ルート検索、一般的な質問など、カレンダーや天気以外の情報を調べるときに使用します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "検索したい内容や質問（例: 「高の原イオンの営業時間」「最近のニュース」「子連れで行けるカフェ」）",
                },
                "search_type": {
                    "type": "string",
                    "enum": [
                        "general",
                        "business_hours",
                        "route",
                        "news",
                        "restaurant",
                    ],
                    "description": "検索の種類。general=一般検索、business_hours=営業時間検索、route=経路検索、news=ニュース検索、restaurant=飲食店検索",
                    "default": "general",
                },
                "location": {
                    "type": "string",
                    "description": "場所（経路検索や店舗検索時に使用）",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "set_reminder",
        "description": "指定した日時にリマインダーを設定します。一度きりの通知や、毎日・毎週の繰り返し通知も設定できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "リマインダーのメッセージ（例: 電話をする、薬を飲む）",
                },
                "date": {
                    "type": "string",
                    "description": "リマインダーの日付（YYYY-MM-DD形式）。繰り返しの場合は開始日。",
                },
                "time": {
                    "type": "string",
                    "description": "リマインダーの時刻（HH:MM形式、例: 10:00）",
                },
                "repeat": {
                    "type": "string",
                    "enum": ["none", "daily", "weekly", "monthly"],
                    "description": "繰り返し設定。none=一度のみ、daily=毎日、weekly=毎週、monthly=毎月",
                    "default": "none",
                },
                "repeat_day": {
                    "type": "string",
                    "enum": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                    "description": "毎週リマインダーの場合の曜日",
                },
            },
            "required": ["message", "date", "time"],
        },
    },
    {
        "name": "list_reminders",
        "description": "設定されているリマインダーの一覧を表示します。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "delete_reminder",
        "description": "指定したIDのリマインダーを削除します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {
                    "type": "string",
                    "description": "削除するリマインダーのID",
                },
            },
            "required": ["reminder_id"],
        },
    },
    {
        "name": "add_shopping_item",
        "description": "買い物リストにアイテムを追加します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "商品名（例: 牛乳、卵、食パン）",
                },
                "quantity": {
                    "type": "string",
                    "description": "数量（例: 2本、1パック）",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "食品",
                        "野菜・果物",
                        "肉・魚",
                        "乳製品",
                        "飲料",
                        "調味料",
                        "日用品",
                        "洗剤・衛生用品",
                        "ベビー用品",
                        "医薬品",
                        "その他",
                    ],
                    "description": "カテゴリ（省略時は自動判定）",
                },
                "note": {
                    "type": "string",
                    "description": "メモ（例: 特売品、〇〇用）",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_shopping",
        "description": "買い物リストを表示します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "カテゴリでフィルタ（省略時は全件）",
                },
            },
        },
    },
    {
        "name": "remove_shopping_item",
        "description": "買い物リストからアイテムを削除します。商品名またはIDで指定できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "item": {
                    "type": "string",
                    "description": "削除する商品名またはID",
                },
            },
            "required": ["item"],
        },
    },
    {
        "name": "search_route",
        "description": "電車・バスの経路や時刻を検索します。出発地から目的地までのルート、所要時間、乗り換え情報を取得できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "出発地（駅名や地名、例: 木津駅、高の原）",
                },
                "destination": {
                    "type": "string",
                    "description": "目的地（駅名や地名、例: 京都駅、奈良駅）",
                },
                "departure_time": {
                    "type": "string",
                    "description": "出発時刻（HH:MM形式、例: 09:00）。省略時は現在時刻",
                },
                "arrival_time": {
                    "type": "string",
                    "description": "到着希望時刻（HH:MM形式、例: 10:30）。指定時はこの時刻に着くルートを検索",
                },
                "date": {
                    "type": "string",
                    "description": "日付（YYYY-MM-DD形式または「明日」「今日」）。省略時は今日",
                },
                "search_type": {
                    "type": "string",
                    "enum": ["normal", "last_train", "first_train"],
                    "description": "検索種類: normal=通常検索、last_train=終電検索、first_train=始発検索",
                    "default": "normal",
                },
            },
            "required": ["origin", "destination"],
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
        web_search_client=None,
        reminder_client=None,
        shopping_list_client=None,
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
            web_search_client: Web検索クライアント
            reminder_client: リマインダークライアント
            shopping_list_client: 買い物リストクライアント
            family_data: 家族情報
            timezone: タイムゾーン
        """
        self.calendar_client = calendar_client
        self.weather_client = weather_client
        self.event_search_client = event_search_client
        self.life_info_client = life_info_client
        self.today_info_client = today_info_client
        self.web_search_client = web_search_client
        self.reminder_client = reminder_client
        self.shopping_list_client = shopping_list_client
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
            "create_calendar_event": self._create_calendar_event,
            "web_search": self._web_search,
            "set_reminder": self._set_reminder,
            "list_reminders": self._list_reminders,
            "delete_reminder": self._delete_reminder,
            "add_shopping_item": self._add_shopping_item,
            "list_shopping": self._list_shopping,
            "remove_shopping_item": self._remove_shopping_item,
            "search_route": self._search_route,
        }

        logger.info("Tool executor initialized")

    async def execute(
        self, tool_name: str, tool_input: dict, tool_use_id: str
    ) -> ToolResult:
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

    async def _create_calendar_event(self, tool_input: dict) -> str:
        """カレンダー予定を作成"""
        if not self.calendar_client:
            return "カレンダークライアントが設定されていません。"

        summary = tool_input.get("summary")
        date_str = tool_input.get("date")
        start_time_str = tool_input.get("start_time")
        end_time_str = tool_input.get("end_time")
        description = tool_input.get("description")
        location = tool_input.get("location")

        if not summary:
            return "予定のタイトルを指定してください。"
        if not date_str:
            return "予定の日付を指定してください。"

        try:
            # 日付をパース
            date = datetime.strptime(date_str, "%Y-%m-%d")
            date = date.replace(tzinfo=ZoneInfo(self.timezone))

            # 終日予定かどうか
            all_day = start_time_str is None

            if all_day:
                start = date
                end = None
            else:
                # 開始時刻をパース
                start_time = datetime.strptime(start_time_str, "%H:%M").time()
                start = datetime.combine(date.date(), start_time)
                start = start.replace(tzinfo=ZoneInfo(self.timezone))

                # 終了時刻をパース（省略時はNone）
                if end_time_str:
                    end_time = datetime.strptime(end_time_str, "%H:%M").time()
                    end = datetime.combine(date.date(), end_time)
                    end = end.replace(tzinfo=ZoneInfo(self.timezone))
                else:
                    end = None

            # イベント作成
            event = await self.calendar_client.create_event(
                summary=summary,
                start=start,
                end=end,
                description=description,
                location=location,
                all_day=all_day,
            )

            # 成功メッセージ
            if all_day:
                time_info = f"{date_str}（終日）"
            else:
                time_info = f"{date_str} {start_time_str}"
                if end_time_str:
                    time_info += f"〜{end_time_str}"

            result = f"予定を登録しました。\n\n【登録内容】\n- タイトル: {summary}\n- 日時: {time_info}"
            if location:
                result += f"\n- 場所: {location}"
            if description:
                result += f"\n- 説明: {description}"

            return result

        except ValueError as e:
            return f"日時の形式が正しくありません: {str(e)}\n日付はYYYY-MM-DD形式、時刻はHH:MM形式で指定してください。"
        except Exception as e:
            logger.error("Failed to create calendar event", error=str(e))
            return f"予定の登録に失敗しました: {str(e)}"

    async def _web_search(self, tool_input: dict) -> str:
        """Web検索を実行"""
        if not self.web_search_client:
            return "Web検索クライアントが設定されていません。"

        query = tool_input.get("query", "")
        search_type = tool_input.get("search_type", "general")
        location = tool_input.get("location", "")

        if not query:
            return "検索クエリを指定してください。"

        try:
            if search_type == "business_hours":
                result = await self.web_search_client.get_business_hours(
                    query, location
                )
            elif search_type == "route":
                # queryを出発地、locationを目的地として解釈
                if location:
                    result = await self.web_search_client.get_route_info(
                        query, location
                    )
                else:
                    result = await self.web_search_client.search(query)
            elif search_type == "news":
                result = await self.web_search_client.get_news(query, location)
            elif search_type == "restaurant":
                result = await self.web_search_client.search_restaurant(
                    cuisine=query, location=location
                )
            else:
                result = await self.web_search_client.general_query(query)

            return f"【Web検索結果】\n{result}"

        except Exception as e:
            logger.error("Web search failed", error=str(e))
            return f"Web検索中にエラーが発生しました: {str(e)}"

    async def _set_reminder(self, tool_input: dict) -> str:
        """リマインダーを設定"""
        if not self.reminder_client:
            return "リマインダークライアントが設定されていません。"

        message = tool_input.get("message", "")
        date_str = tool_input.get("date", "")
        time_str = tool_input.get("time", "")
        repeat = tool_input.get("repeat", "none")
        repeat_day = tool_input.get("repeat_day")

        if not message:
            return "リマインダーのメッセージを指定してください。"
        if not date_str:
            return "日付を指定してください。"
        if not time_str:
            return "時刻を指定してください。"

        try:
            # 日時をパース
            date = datetime.strptime(date_str, "%Y-%m-%d")
            time = datetime.strptime(time_str, "%H:%M").time()
            trigger_time = datetime.combine(date.date(), time)
            trigger_time = trigger_time.replace(tzinfo=ZoneInfo(self.timezone))

            # 繰り返し設定を変換
            repeat_setting = None if repeat == "none" else repeat

            # リマインダーを追加
            reminder = await self.reminder_client.add_reminder(
                message=message,
                trigger_time=trigger_time,
                repeat=repeat_setting,
                repeat_day=repeat_day,
            )

            # 成功メッセージ
            result = f"リマインダーを設定しました。\n\n"
            result += f"【設定内容】\n"
            result += f"- ID: {reminder.id}\n"
            result += f"- メッセージ: {message}\n"

            if repeat_setting == "daily":
                result += f"- 時刻: 毎日 {time_str}"
            elif repeat_setting == "weekly":
                day_names = {
                    "mon": "月曜",
                    "tue": "火曜",
                    "wed": "水曜",
                    "thu": "木曜",
                    "fri": "金曜",
                    "sat": "土曜",
                    "sun": "日曜",
                }
                day_name = (
                    day_names.get(repeat_day, repeat_day) if repeat_day else "指定なし"
                )
                result += f"- 時刻: 毎週{day_name} {time_str}"
            elif repeat_setting == "monthly":
                result += f"- 時刻: 毎月{date.day}日 {time_str}"
            else:
                result += f"- 日時: {date_str} {time_str}"

            return result

        except ValueError as e:
            return f"日時の形式が正しくありません: {str(e)}\n日付はYYYY-MM-DD形式、時刻はHH:MM形式で指定してください。"
        except Exception as e:
            logger.error("Failed to set reminder", error=str(e))
            return f"リマインダーの設定に失敗しました: {str(e)}"

    async def _list_reminders(self, tool_input: dict) -> str:
        """リマインダー一覧を取得"""
        if not self.reminder_client:
            return "リマインダークライアントが設定されていません。"

        return self.reminder_client.format_all_reminders()

    async def _delete_reminder(self, tool_input: dict) -> str:
        """リマインダーを削除"""
        if not self.reminder_client:
            return "リマインダークライアントが設定されていません。"

        reminder_id = tool_input.get("reminder_id", "")
        if not reminder_id:
            return "リマインダーIDを指定してください。"

        # 削除前に存在確認
        reminder = self.reminder_client.get_reminder(reminder_id)
        if not reminder:
            return f"ID '{reminder_id}' のリマインダーは見つかりませんでした。"

        success = await self.reminder_client.delete_reminder(reminder_id)
        if success:
            return f"リマインダー「{reminder.message}」を削除しました。"
        else:
            return f"リマインダーの削除に失敗しました。"

    async def _add_shopping_item(self, tool_input: dict) -> str:
        """買い物リストにアイテムを追加"""
        if not self.shopping_list_client:
            return "買い物リストクライアントが設定されていません。"

        name = tool_input.get("name", "")
        quantity = tool_input.get("quantity", "")
        category = tool_input.get("category")
        note = tool_input.get("note", "")

        if not name:
            return "商品名を指定してください。"

        try:
            item = self.shopping_list_client.add_item(
                name=name,
                quantity=quantity,
                category=category,
                note=note,
            )

            result = f"買い物リストに追加しました。\n\n"
            result += f"【追加内容】\n"
            result += f"- 商品名: {item.name}\n"
            if item.quantity:
                result += f"- 数量: {item.quantity}\n"
            result += f"- カテゴリ: {item.category}\n"
            result += f"- ID: {item.id}"

            return result

        except Exception as e:
            logger.error("Failed to add shopping item", error=str(e))
            return f"買い物リストへの追加に失敗しました: {str(e)}"

    async def _list_shopping(self, tool_input: dict) -> str:
        """買い物リストを表示"""
        if not self.shopping_list_client:
            return "買い物リストクライアントが設定されていません。"

        category = tool_input.get("category")
        return self.shopping_list_client.format_list(category)

    async def _remove_shopping_item(self, tool_input: dict) -> str:
        """買い物リストからアイテムを削除"""
        if not self.shopping_list_client:
            return "買い物リストクライアントが設定されていません。"

        item_str = tool_input.get("item", "")
        if not item_str:
            return "削除する商品名またはIDを指定してください。"

        # まずIDとして試す
        item = self.shopping_list_client.get_item(item_str)
        if item:
            self.shopping_list_client.remove_item(item_str)
            return f"「{item.name}」を買い物リストから削除しました。"

        # 商品名として試す
        removed_item = self.shopping_list_client.remove_item_by_name(item_str)
        if removed_item:
            return f"「{removed_item.name}」を買い物リストから削除しました。"

        return f"「{item_str}」は買い物リストに見つかりませんでした。"

    async def _search_route(self, tool_input: dict) -> str:
        """交通経路を検索"""
        if not self.web_search_client:
            return "交通情報検索にはWeb検索クライアントが必要です。"

        origin = tool_input.get("origin", "")
        destination = tool_input.get("destination", "")
        departure_time = tool_input.get("departure_time", "")
        arrival_time = tool_input.get("arrival_time", "")
        date = tool_input.get("date", "今日")
        search_type = tool_input.get("search_type", "normal")

        if not origin:
            return "出発地を指定してください。"
        if not destination:
            return "目的地を指定してください。"

        try:
            # 検索クエリを構築
            if search_type == "last_train":
                query = f"{origin}から{destination}までの終電を教えてください。最終の電車・バスの時刻と乗り換え情報を含めてください。"
            elif search_type == "first_train":
                query = f"{origin}から{destination}までの始発を教えてください。最初の電車・バスの時刻と乗り換え情報を含めてください。"
            elif arrival_time:
                query = f"{date}に{arrival_time}までに{destination}に着きたいです。{origin}からの電車・バスの経路と出発時刻を教えてください。乗り換え情報と所要時間も含めてください。"
            elif departure_time:
                query = f"{date}の{departure_time}頃に{origin}を出発して{destination}に行きたいです。電車・バスの経路を教えてください。乗り換え情報と所要時間も含めてください。"
            else:
                query = f"{origin}から{destination}までの電車・バスの経路を教えてください。現在時刻からのルート、所要時間、乗り換え情報を含めてください。"

            # Perplexity APIで検索
            result = await self.web_search_client.search(query)

            return f"【交通情報検索結果】\n{origin} → {destination}\n\n{result}"

        except Exception as e:
            logger.error("Route search failed", error=str(e))
            return f"交通情報の検索に失敗しました: {str(e)}"


def get_tool_definitions() -> list[dict]:
    """ツール定義を取得"""
    return TOOL_DEFINITIONS
