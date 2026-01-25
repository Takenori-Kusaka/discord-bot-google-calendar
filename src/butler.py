"""Butler Core - 執事「黒田」のコアロジック

LangGraphモードが有効な場合は、LangGraphベースのエージェントを使用します。
無効な場合は、既存のClaudeClient.chat_with_toolsを使用します。
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import yaml

from .agents.graph import run_butler_agent
from .agents.tools import ToolExecutor, get_tool_definitions
from .clients.calendar import CalendarEvent, GoogleCalendarClient
from .clients.claude import ClaudeClient
from .clients.discord import DiscordClient
from .clients.event_search import EventSearchClient
from .clients.expense import ExpenseClient
from .clients.health import HealthClient
from .clients.home_assistant import HomeAssistantClient
from .clients.housework import HouseworkClient
from .clients.life_info import LifeInfoClient
from .clients.reminder import ReminderClient
from .clients.school import SchoolClient
from .clients.shopping_list import ShoppingListClient
from .clients.today_info import TodayInfoClient
from .clients.weather import WeatherClient
from .clients.web_search import WebSearchClient
from .config.settings import Settings
from .utils.logger import get_logger

logger = get_logger(__name__)

# 家族情報ファイルパス
FAMILY_DATA_PATH = "docs/personal/data/family.yml"


class Butler:
    """執事「黒田」"""

    def __init__(
        self,
        settings: Settings,
        calendar_client: GoogleCalendarClient,
        claude_client: ClaudeClient,
        discord_client: DiscordClient,
        event_search_client: Optional[EventSearchClient] = None,
        weather_client: Optional[WeatherClient] = None,
        today_info_client: Optional[TodayInfoClient] = None,
        life_info_client: Optional[LifeInfoClient] = None,
        web_search_client: Optional[WebSearchClient] = None,
        reminder_client: Optional[ReminderClient] = None,
        shopping_list_client: Optional[ShoppingListClient] = None,
        housework_client: Optional[HouseworkClient] = None,
        home_assistant_client: Optional[HomeAssistantClient] = None,
        expense_client: Optional[ExpenseClient] = None,
        school_client: Optional[SchoolClient] = None,
        health_client: Optional[HealthClient] = None,
        use_langgraph: bool = False,
    ):
        """初期化

        Args:
            settings: アプリケーション設定
            calendar_client: Google Calendarクライアント
            claude_client: Claudeクライアント
            discord_client: Discordクライアント
            event_search_client: イベント検索クライアント（オプション）
            weather_client: 天気クライアント（オプション）
            today_info_client: 今日は何の日クライアント（オプション）
            life_info_client: 生活影響情報クライアント（オプション）
            web_search_client: Web検索クライアント（オプション）
            reminder_client: リマインダークライアント（オプション）
            shopping_list_client: 買い物リストクライアント（オプション）
            housework_client: 家事記録クライアント（オプション）
            home_assistant_client: Home Assistantクライアント（オプション）
            expense_client: 家計簿クライアント（オプション）
            school_client: 学校情報クライアント（オプション）
            health_client: 健康記録クライアント（オプション）
            use_langgraph: LangGraphエージェントを使用するかどうか
        """
        self.settings = settings
        self.calendar = calendar_client
        self.claude = claude_client
        self.discord = discord_client
        self.event_search = event_search_client
        self.weather = weather_client
        self.today_info = today_info_client
        self.life_info = life_info_client
        self.web_search = web_search_client
        self.reminder = reminder_client
        self.shopping_list = shopping_list_client
        self.housework = housework_client
        self.home_assistant = home_assistant_client
        self.expense = expense_client
        self.school = school_client
        self.health = health_client
        self.name = settings.butler_name
        self.use_langgraph = use_langgraph

        # 状態保存パス
        self.state_path = self._get_state_path()

        # フィルタリングルールを読み込み
        self.ignore_patterns = self._load_rules("config/ignore_rules.yml")
        self.notify_patterns = self._load_rules("config/notify_rules.yml")

        # 家族情報を読み込み
        self.family_data = self._load_family_data()

        # ツール実行器を初期化
        self.tool_executor = ToolExecutor(
            calendar_client=calendar_client,
            weather_client=weather_client,
            event_search_client=event_search_client,
            life_info_client=life_info_client,
            today_info_client=today_info_client,
            web_search_client=web_search_client,
            reminder_client=reminder_client,
            shopping_list_client=shopping_list_client,
            housework_client=housework_client,
            home_assistant_client=home_assistant_client,
            expense_client=expense_client,
            school_client=school_client,
            health_client=health_client,
            family_data=self.family_data,
            timezone=settings.timezone,
        )

        # ツール定義を取得
        self.tools = get_tool_definitions()

        # Discordメッセージハンドラを登録
        self.discord.set_message_handler(self.handle_message)

        mode = "LangGraph" if self.use_langgraph else "Claude直接"
        logger.info(
            f"執事「{self.name}」、準備完了でございます。"
            f"（ツール数: {len(self.tools)}、モード: {mode}）"
        )

    def _load_rules(self, path: str) -> list[str]:
        """ルールファイルを読み込み

        Args:
            path: ルールファイルのパス

        Returns:
            list[str]: パターンリスト
        """
        try:
            file_path = Path(path)
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    return data.get("patterns", []) if data else []
        except Exception as e:
            logger.warning(f"Failed to load rules from {path}", error=str(e))
        return []

    def _load_family_data(self) -> dict[str, Any]:
        """家族情報を読み込み

        Returns:
            dict: 家族情報
        """
        try:
            file_path = Path(FAMILY_DATA_PATH)
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    logger.info("Family data loaded")
                    return data or {}
        except Exception as e:
            logger.warning(f"Failed to load family data: {e}")
        return {}

    def _get_state_path(self) -> Path:
        """状態保存パスを取得"""
        log_dir = self.settings.log_dir or Path(".")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir / "butler_state.json"
        except Exception:
            return Path("butler_state.json")

    def _load_state(self) -> dict[str, Any]:
        """状態を読み込み"""
        try:
            if self.state_path.exists():
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("Failed to load state", error=str(e))
        return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        """状態を保存"""
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save state", error=str(e))

    def _weekly_event_key(self, now: datetime) -> str:
        """週次イベント用のキーを生成"""
        iso_year, iso_week, _ = now.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

    def _hash_message(self, message: str) -> str:
        return hashlib.sha256(message.strip().encode("utf-8")).hexdigest()

    async def _should_skip_weekly_event_notification(self, message: str) -> bool:
        """週次イベント通知の重複判定"""
        now = datetime.now(ZoneInfo(self.settings.timezone))
        state = self._load_state()
        last = state.get("weekly_events", {})
        week_key = self._weekly_event_key(now)
        message_hash = self._hash_message(message)

        if last.get("week_key") == week_key and last.get("hash") == message_hash:
            logger.info("Weekly event notification already sent (state)")
            return True

        # Discord上の最新メッセージと比較
        is_dup = await self.discord.is_duplicate_message(
            self.settings.discord_channel_region,
            message,
        )
        if is_dup:
            logger.info("Weekly event notification already sent (channel history)")
            return True

        return False

    def _record_weekly_event_sent(self, message: str) -> None:
        """週次イベント通知の送信記録"""
        now = datetime.now(ZoneInfo(self.settings.timezone))
        state = self._load_state()
        state["weekly_events"] = {
            "week_key": self._weekly_event_key(now),
            "hash": self._hash_message(message),
            "sent_at": now.isoformat(),
        }
        self._save_state(state)

    def _get_family_context(self) -> str:
        """家族情報をコンテキスト文字列に変換"""
        if not self.family_data:
            return ""

        lines = []

        # ごみ捨て情報
        garbage = self.family_data.get("garbage", {})
        if garbage:
            lines.append("### ごみ捨てルール")
            for schedule in garbage.get("schedule", []):
                lines.append(
                    f"- {schedule.get('type', '')}: {schedule.get('days', schedule.get('frequency', ''))}"
                )

        # お気に入りの場所
        location = self.family_data.get("location", {})
        if location.get("favorite_places"):
            lines.append("\n### よく行く場所")
            for place in location["favorite_places"]:
                lines.append(f"- {place.get('name', '')}: {place.get('type', '')}")

        return "\n".join(lines)

    async def morning_notification(self) -> None:
        """朝の予定通知を実行"""
        logger.info("Starting morning notification")

        try:
            # 1. 今日の予定を取得
            events = await self.calendar.get_today_events()
            logger.info(f"Retrieved {len(events)} events for today")

            # 2. 重要な予定をフィルタリング
            important_events = await self.claude.filter_important_events(
                events,
                ignore_patterns=self.ignore_patterns,
                notify_patterns=self.notify_patterns,
            )
            logger.info(f"Filtered to {len(important_events)} important events")

            # 3. 天気情報を取得
            weather_info = None
            if self.weather:
                weather_info = await self.weather.get_today_weather()
                if weather_info:
                    logger.info(f"Weather: {weather_info.weather_description}")

            # 4. 今日は何の日を取得
            today_info = None
            if self.today_info:
                today_info = await self.today_info.get_today_info()
                if today_info:
                    logger.info(f"Today: {today_info.anniversary}")

            # 5. 執事口調のメッセージを生成
            message = await self.claude.generate_butler_message(
                important_events,
                butler_name=self.name,
            )

            # 6. 天気情報を追加
            if weather_info:
                weather_section = (
                    f"\n\n【本日の天気】\n{weather_info.format_for_notification()}"
                )
                message = message + weather_section

            # 7. 今日は何の日を追加
            if today_info:
                today_section = (
                    f"\n\n【豆知識】\n{today_info.format_for_notification()}"
                )
                message = message + today_section

            # 8. Discordに送信
            success = await self.discord.send_to_channel(
                self.settings.discord_channel_schedule,
                message,
            )

            if success:
                logger.info("Morning notification sent successfully")
            else:
                raise Exception("Failed to send message to Discord")

        except Exception as e:
            logger.error("Morning notification failed", error=str(e))
            # エラー通知
            await self.discord.send_error_notification(
                e,
                context="朝の予定通知",
            )

    async def weekly_event_notification(self) -> None:
        """週次の地域イベント通知を実行"""
        logger.info("Starting weekly event notification")

        if not self.event_search:
            logger.warning("Event search client not configured, skipping")
            return

        try:
            # 1. 地域イベントを検索
            search_results = await self.event_search.search_events()
            logger.info(f"Retrieved {len(search_results)} search results")

            # 2. 検索結果からイベント情報を抽出
            events = await self.claude.extract_events_from_search(search_results)
            logger.info(f"Extracted {len(events)} events from Claude")

            # 抽出失敗時はフォールバックを生成
            if not events and search_results:
                logger.warning(
                    "Claude extraction returned empty, falling back to build_events_from_results",
                    search_results_count=len(search_results),
                )
                events = self.event_search.build_events_from_results(search_results)
                logger.info(f"Events built from results: {len(events)}")

            if not events:
                logger.warning(
                    "No events found from any source, using reference events as fallback"
                )
                events = self.event_search.build_reference_events()
                logger.info(f"Reference events built: {len(events)}")

            # 3. 家族向けおすすめメッセージを生成
            message = await self.claude.generate_event_recommendation(
                events,
                butler_name=self.name,
            )

            # 4. 参考リンクを追加
            reference_links = self.event_search.format_reference_links()
            if reference_links:
                message = message + reference_links

            # 重複チェック
            if await self._should_skip_weekly_event_notification(message):
                return

            # 5. Discordに送信
            success = await self.discord.send_to_channel(
                self.settings.discord_channel_region,
                message,
            )

            if success:
                logger.info("Weekly event notification sent successfully")
                self._record_weekly_event_sent(message)
            else:
                raise Exception("Failed to send message to Discord")

        except Exception as e:
            logger.error("Weekly event notification failed", error=str(e))
            # エラー通知
            await self.discord.send_error_notification(
                e,
                context="週次イベント通知",
            )

    async def weekly_life_info_notification(self) -> None:
        """週次の生活影響情報通知を実行"""
        logger.info("Starting weekly life info notification")

        if not self.life_info:
            logger.warning("Life info client not configured, skipping")
            return

        try:
            # 1. 生活影響情報を取得
            life_info_list = await self.life_info.get_all_life_info()
            logger.info(f"Retrieved {len(life_info_list)} life info items")

            if not life_info_list:
                logger.info("No life info items to notify")
                return

            # 2. 通知メッセージを生成
            info_section = self.life_info.format_for_weekly_notification(life_info_list)

            # 3. 執事口調の導入文を生成
            intro = (
                f"旦那様、執事の{self.name}でございます。\n"
                "今週の生活に関わる重要な情報をお届けいたします。\n"
            )
            message = intro + "\n" + info_section

            # 4. Discordに送信（生活影響情報用チャンネル）
            # 設定にチャンネルがなければ地域チャンネルに送信
            channel = (
                getattr(self.settings, "discord_channel_life_info", None)
                or self.settings.discord_channel_region
            )

            success = await self.discord.send_to_channel(channel, message)

            if success:
                logger.info("Weekly life info notification sent successfully")
            else:
                raise Exception("Failed to send message to Discord")

        except Exception as e:
            logger.error("Weekly life info notification failed", error=str(e))
            # エラー通知
            await self.discord.send_error_notification(
                e,
                context="週次生活影響情報通知",
            )

    async def handle_message(
        self, message: str, channel: str, images: list | None = None
    ) -> str:
        """Discordメッセージを処理（ツール使用対応）

        Args:
            message: 受信したメッセージ
            channel: チャンネル名
            images: 添付画像のリスト（base64エンコード済み）

        Returns:
            str: 応答メッセージ
        """
        mode = "LangGraph" if self.use_langgraph else "Claude直接"
        logger.info(
            "Handling message",
            message_length=len(message),
            channel=channel,
            mode=mode,
            image_count=len(images) if images else 0,
        )

        try:
            # 家族情報コンテキストを取得
            family_context = self._get_family_context()

            if self.use_langgraph:
                # LangGraphエージェントを使用
                response = await run_butler_agent(
                    message=message,
                    tool_executor=self.tool_executor,
                    butler_name=self.name,
                    user_context={"family_context": family_context},
                    images=images,
                )
            else:
                # 既存のClaudeClient.chat_with_toolsを使用
                response = await self.claude.chat_with_tools(
                    message=message,
                    channel=channel,
                    tools=self.tools,
                    tool_executor=self.tool_executor,
                    butler_name=self.name,
                    family_context=family_context,
                )

            logger.info("Message handled successfully", response_length=len(response))
            return response

        except Exception as e:
            logger.error("Failed to handle message", error=str(e))
            return (
                f"恐れ入ります、執事の{self.name}でございます。"
                "ただいま処理中にエラーが発生いたしました。"
                "しばらくしてから再度お申し付けくださいませ。"
            )
