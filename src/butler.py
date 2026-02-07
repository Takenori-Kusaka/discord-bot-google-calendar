"""Butler Core - 執事「黒田」のコアロジック

LangGraphモードが有効な場合は、LangGraphベースのエージェントを使用します。
無効な場合は、既存のClaudeClient.chat_with_toolsを使用します。
"""

import hashlib
import json
from datetime import datetime, timedelta
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
from .clients.maps import GoogleMapsClient
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

# コーチング用ファイルパス
CHILDCARE_PLAN_PATH = "docs/personal/data/childcare_leave_plan_2026.md"
PROFILE_PATH = "docs/personal/data/profile.yml"
CHILDCARE_WEEKLY_LOG_PATH = "docs/personal/data/childcare_leave_weekly_log.md"


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
        maps_client: Optional[GoogleMapsClient] = None,
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
            maps_client: Google Mapsクライアント（オプション）
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
        self.maps = maps_client
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
            maps_client=maps_client,
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

    # =========================================================================
    # コーチング機能
    # =========================================================================

    def _get_coaching_phase_info(self) -> dict[str, Any]:
        """現在の育休フェーズ・週番号を算出"""
        from datetime import date

        start_date = date(2026, 1, 26)
        end_date = date(2026, 9, 18)
        now = datetime.now(ZoneInfo(self.settings.timezone))
        today = now.date()

        days_elapsed = (today - start_date).days
        week_number = max(1, days_elapsed // 7 + 1)
        total_weeks = 34

        if week_number <= 10:
            phase, phase_name = 1, "回復期"
            phase_purpose = "体調を回復し、回復の3段階（睡眠→趣味→運動）を順番に進める"
        elif week_number <= 18:
            phase, phase_name = 2, "再構築期"
            phase_purpose = "運動習慣を確立し、持続可能な家事育児体制を構築する"
        elif week_number <= 27:
            phase, phase_name = 3, "探索期"
            phase_purpose = "社外との接点を増やし、キャリアの方向性を検討する"
        else:
            phase, phase_name = 4, "準備期"
            phase_purpose = "復帰に向けた準備を整え、持続可能な働き方を設計する"

        days_remaining = (end_date - today).days
        total_days = (end_date - start_date).days
        progress_pct = min(100, max(0, int(days_elapsed / total_days * 100)))

        weekday_names = [
            "月曜日",
            "火曜日",
            "水曜日",
            "木曜日",
            "金曜日",
            "土曜日",
            "日曜日",
        ]

        return {
            "week_number": week_number,
            "total_weeks": total_weeks,
            "phase": phase,
            "phase_name": phase_name,
            "phase_purpose": phase_purpose,
            "days_remaining": days_remaining,
            "progress_pct": progress_pct,
            "today": today.isoformat(),
            "day_of_week": weekday_names[today.weekday()],
        }

    def _load_coaching_context(self) -> dict[str, str]:
        """コーチング用コンテキストファイルを読み込み"""
        context = {}
        file_map = {
            "childcare_plan": CHILDCARE_PLAN_PATH,
            "profile": PROFILE_PATH,
            "weekly_log": CHILDCARE_WEEKLY_LOG_PATH,
        }
        for key, path_str in file_map.items():
            try:
                file_path = Path(path_str)
                if file_path.exists():
                    context[key] = file_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(
                    f"Failed to load coaching context: {path_str}", error=str(e)
                )
        return context

    def _parse_daily_report(self, text: str) -> dict[str, Any]:
        """日報テキストから構造化データを抽出

        対応フォーマット:
            睡眠: 8時間
            体調: 7/10
            一人時間: 2時間
            やったこと: 読書、散歩
            気づき: よく眠れた
        """
        import re

        data: dict[str, Any] = {"raw": text}

        # 睡眠時間
        m = re.search(r"睡眠[:：]\s*([\d.]+)", text)
        if m:
            data["sleep_hours"] = float(m.group(1))

        # 体調 (1-10)
        m = re.search(r"体調[:：]\s*([\d.]+)", text)
        if m:
            data["condition"] = float(m.group(1))

        # 一人時間
        m = re.search(r"一人時間[:：]\s*([\d.]+)", text)
        if m:
            data["alone_hours"] = float(m.group(1))

        # やったこと
        m = re.search(r"やったこと[:：]\s*(.+?)(?:\n|気づき|$)", text, re.DOTALL)
        if m:
            data["activities"] = m.group(1).strip()

        # 気づき
        m = re.search(r"気づき[:：]\s*(.+)", text, re.DOTALL)
        if m:
            data["notes"] = m.group(1).strip()

        return data

    def _save_daily_report(
        self, report_date: str, content: str, parsed: dict[str, Any] | None = None
    ) -> None:
        """日報を butler_state.json に構造化保存"""
        state = self._load_state()
        coaching = state.setdefault("coaching", {})
        reports = coaching.setdefault("daily_reports", {})

        entry: dict[str, Any] = {
            "content": content,
            "reported_at": datetime.now(ZoneInfo(self.settings.timezone)).isoformat(),
        }
        if parsed:
            for key in (
                "sleep_hours",
                "condition",
                "alone_hours",
                "activities",
                "notes",
            ):
                if key in parsed:
                    entry[key] = parsed[key]

        reports[report_date] = entry

        # 直近30日分のみ保持
        if len(reports) > 30:
            for key in sorted(reports.keys())[:-30]:
                del reports[key]

        self._save_state(state)

    def _get_recent_reports(self, days: int = 7) -> dict[str, Any]:
        """直近の日報を取得"""
        state = self._load_state()
        reports = state.get("coaching", {}).get("daily_reports", {})
        cutoff = (
            (datetime.now(ZoneInfo(self.settings.timezone)) - timedelta(days=days))
            .date()
            .isoformat()
        )
        return {k: v for k, v in reports.items() if k >= cutoff}

    def _format_reports_for_prompt(self, reports: dict[str, Any]) -> str:
        """日報データをコーチングプロンプト用にフォーマット"""
        if not reports:
            return ""

        lines = []
        sleep_vals = []
        condition_vals = []
        alone_vals = []

        for date_str, r in sorted(reports.items()):
            parts = [f"- {date_str}:"]
            if "sleep_hours" in r:
                parts.append(f"睡眠{r['sleep_hours']}h")
                sleep_vals.append(r["sleep_hours"])
            if "condition" in r:
                parts.append(f"体調{r['condition']}/10")
                condition_vals.append(r["condition"])
            if "alone_hours" in r:
                parts.append(f"一人時間{r['alone_hours']}h")
                alone_vals.append(r["alone_hours"])
            if "activities" in r:
                parts.append(r["activities"][:100])
            elif "content" in r:
                parts.append(r["content"][:100])
            lines.append(" / ".join(parts))

        # トレンドサマリー
        summary_parts = []
        if sleep_vals:
            avg = sum(sleep_vals) / len(sleep_vals)
            summary_parts.append(f"平均睡眠: {avg:.1f}時間")
        if condition_vals:
            avg = sum(condition_vals) / len(condition_vals)
            summary_parts.append(f"平均体調: {avg:.1f}/10")
        if alone_vals:
            total = sum(alone_vals)
            summary_parts.append(f"一人時間合計: {total:.1f}時間")

        if summary_parts:
            lines.append(
                f"\n【直近{len(reports)}日間のトレンド】 {' / '.join(summary_parts)}"
            )

        return "\n".join(lines)

    def _build_coaching_prompt(
        self,
        phase_info: dict[str, Any],
        coaching_context: dict[str, str],
        recent_reports: str,
        today_events: str,
    ) -> str:
        """コーチング用プロンプトを構築"""
        plan_text = coaching_context.get(
            "childcare_plan", "（育休計画ファイルが見つかりません）"
        )
        profile_text = coaching_context.get(
            "profile", "（プロファイルが見つかりません）"
        )
        weekly_log = coaching_context.get("weekly_log", "")

        return f"""あなたは日下家に仕える執事「{self.name}」であり、旦那様（日下武紀様）の
育休期間中のパーソナルコーチでもあります。

## あなたの役割
- 育休計画に基づいた毎朝のコーチングメッセージを作成する
- 執事らしい丁寧だが温かみのある口調で、押しつけがましくなく導く
- 旦那様の体調回復を最優先に、無理をさせない
- 「何もしない」ことも回復には必要だと理解している

## 今日の情報
- 日付: {phase_info['today']}（{phase_info['day_of_week']}）
- 育休 Week {phase_info['week_number']} / {phase_info['total_weeks']}
- Phase {phase_info['phase']}: {phase_info['phase_name']}
- Phase目的: {phase_info['phase_purpose']}
- 復帰まで残り {phase_info['days_remaining']} 日（進捗: {phase_info['progress_pct']}%）

## 今日のカレンダー予定
{today_events if today_events else "特にございません。"}

## 旦那様の一日のスケジュール（育休中・短時間保育）
- 05:40 起床
- 06:04 ラジオ体操
- 06:20 朝食
- 08:15 お嬢様の保育園送り
- 08:30〜16:00 自由時間（コーチングの主要対象）
  ※坊ちゃま（0歳）のお世話は随時
- 16:00 お迎え準備
- 16:15 お嬢様お迎え
- 17:00〜21:30 夕方〜夜ルーティン（固定スケジュール）
- 21:30 就寝

## 直近の日報
{recent_reports if recent_reports else "まだ日報の提出はございません。"}

## 育休計画（全文）
{plan_text}

## 旦那様のプロファイル
{profile_text}

## 週次振り返りログ
{weekly_log if weekly_log else "まだ週次振り返りは記録されておりません。"}

## メッセージ作成ルール
1. 挨拶から始める（「旦那様、おはようございます。執事の{self.name}でございます。」）
2. 現在のPhase/Week位置と、今週の主要タスクを簡潔に伝える
3. 今日の自由時間（08:30-16:00）の過ごし方を提案する（無理のない範囲で）
4. 現在のPhaseに応じた具体的なアクション提案（1-2個）
5. 体調・回復に関するリマインダー（睡眠優先の場合は特に）
6. 締めの言葉（温かく、プレッシャーを与えない）
7. 絵文字は使用しない
8. 400-600文字程度に収める
9. 日報がある場合はその進捗を踏まえたコメントを含める
10. カレンダーに予定がある場合は、自由時間への影響を考慮する
11. メッセージの最後に、日報テンプレートを案内する（以下の形式で）:
    「本日の振り返りは以下のテンプレートでお知らせくださいませ。」
    @黒田【日報】
    睡眠: ○時間
    体調: ○/10
    一人時間: ○時間
    やったこと: 自由記述
    気づき: 任意
    ※全項目を埋める必要はなく、「やったこと」だけでも結構です

## 重要な注意
- 旦那様は3年連続で体調を崩しており、回復を最優先にすべき
- 運転不可（精神疾患による意識消失のリスク）
- 「何もしない」日があっても否定しない
- 反復作業を嫌う認知特性を考慮する
- 知的刺激への渇望を活用する
"""

    async def daily_coaching_notification(self) -> None:
        """デイリーコーチング通知を実行"""
        logger.info("Starting daily coaching notification")

        try:
            # 1. Phase/Week情報を取得
            phase_info = self._get_coaching_phase_info()
            logger.info(
                "Coaching phase info",
                week=phase_info["week_number"],
                phase=phase_info["phase"],
            )

            # 育休期間外ならスキップ
            if phase_info["days_remaining"] < 0 or phase_info["week_number"] < 1:
                logger.info("Outside childcare leave period, skipping coaching")
                return

            # 2. コンテキストファイルを読み込み
            coaching_context = self._load_coaching_context()

            # 3. 直近の日報を取得
            recent_reports = self._get_recent_reports(days=7)
            reports_text = self._format_reports_for_prompt(recent_reports)

            # 4. 今日のカレンダー予定を取得
            today_events = await self.calendar.get_today_events()
            events_text = ""
            if today_events:
                events_text = "\n".join(
                    f"- {e.start.strftime('%H:%M') if not e.all_day else '終日'}: {e.summary}"
                    for e in today_events
                )

            # 5. コーチングプロンプトを構築
            prompt = self._build_coaching_prompt(
                phase_info=phase_info,
                coaching_context=coaching_context,
                recent_reports=reports_text,
                today_events=events_text,
            )

            # 6. Claude APIでメッセージ生成
            response = self.claude.client.messages.create(
                model=self.claude.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            message = response.content[0].text

            # 7. Discordに送信
            success = await self.discord.send_to_channel(
                self.settings.discord_channel_coaching,
                message,
            )

            if success:
                logger.info("Daily coaching notification sent successfully")
                state = self._load_state()
                coaching = state.setdefault("coaching", {})
                coaching["last_sent"] = datetime.now(
                    ZoneInfo(self.settings.timezone)
                ).isoformat()
                self._save_state(state)
            else:
                raise Exception("Failed to send coaching message to Discord")

        except Exception as e:
            logger.error("Daily coaching notification failed", error=str(e))
            await self.discord.send_error_notification(
                e,
                context="デイリーコーチング通知",
            )

    async def _handle_daily_report(self, message: str) -> str:
        """日報を処理してフィードバックを返す"""
        logger.info("Processing daily report", message_length=len(message))

        now = datetime.now(ZoneInfo(self.settings.timezone))
        report_date = now.date().isoformat()

        # 【日報】タグの後のテキストを取得
        report_content = message.split("【日報】", 1)[-1].strip()
        if not report_content:
            return (
                f"旦那様、執事の{self.name}でございます。\n"
                "日報の内容が空でございます。\n"
                "以下のテンプレートをご参考にどうぞ。\n\n"
                "```\n"
                "@黒田【日報】\n"
                "睡眠: ○時間\n"
                "体調: ○/10\n"
                "一人時間: ○時間\n"
                "やったこと: 自由記述\n"
                "気づき: 任意\n"
                "```"
            )

        # 構造化パース
        parsed = self._parse_daily_report(report_content)

        # 日報を構造化保存
        self._save_daily_report(report_date, report_content, parsed)

        # 直近の日報でトレンドを取得
        recent_reports = self._get_recent_reports(days=7)
        trend_text = self._format_reports_for_prompt(recent_reports)

        # Phase情報を取得
        phase_info = self._get_coaching_phase_info()

        # パースされた数値のサマリー
        parsed_summary = ""
        if "sleep_hours" in parsed:
            parsed_summary += f"- 睡眠: {parsed['sleep_hours']}時間\n"
        if "condition" in parsed:
            parsed_summary += f"- 体調: {parsed['condition']}/10\n"
        if "alone_hours" in parsed:
            parsed_summary += f"- 一人時間: {parsed['alone_hours']}時間\n"

        # フィードバック生成用プロンプト
        prompt = f"""あなたは日下家に仕える執事「{self.name}」であり、
旦那様の育休コーチです。

旦那様から本日の日報が提出されました。
コーチとして、温かく、建設的なフィードバックを返してください。

## 現在の位置
- Week {phase_info['week_number']} / Phase {phase_info['phase']}: {phase_info['phase_name']}
- Phase目的: {phase_info['phase_purpose']}

## 本日の日報（原文）
{report_content}

## パースされた数値
{parsed_summary if parsed_summary else "（数値データなし — 自由記述形式）"}

## 直近の日報トレンド
{trend_text if trend_text else "本日が初回の日報です。"}

## フィードバックルール
1. 日報の提出自体を称える
2. 数値データがある場合はトレンドに言及（睡眠8時間以上を推奨、等）
3. 活動内容に対する具体的なコメント
4. Phase目標との関連性を指摘（該当する場合）
5. 改善提案は控えめに、ポジティブに
6. 執事口調（丁寧で温かみのある言葉遣い）
7. 絵文字は使用しない
8. 200-300文字程度に収める
"""

        try:
            response = self.claude.client.messages.create(
                model=self.claude.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error("Failed to generate daily report feedback", error=str(e))
            return (
                f"旦那様、執事の{self.name}でございます。\n"
                f"本日の日報、確かに承りました。\n"
                f"（{report_date}分として記録いたしました）"
            )

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
            # 日報検出（コーチングチャンネルで「【日報】」を含むメッセージ）
            if (
                channel == self.settings.discord_channel_coaching
                and "【日報】" in message
            ):
                return await self._handle_daily_report(message)

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
