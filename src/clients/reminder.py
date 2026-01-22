"""リマインダークライアント

リマインダーの登録、削除、一覧表示、およびスケジュール実行を管理します。
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from zoneinfo import ZoneInfo

from ..utils.logger import get_logger

logger = get_logger(__name__)

# リマインダーデータ保存パス
REMINDERS_FILE = "data/reminders.json"


@dataclass
class Reminder:
    """リマインダー"""

    id: str
    message: str
    trigger_time: str  # ISO形式の日時文字列
    repeat: Optional[str] = None  # "daily", "weekly", "monthly", None(一度のみ)
    repeat_day: Optional[str] = None  # 曜日（weekly用）: "mon", "tue", etc.
    repeat_time: Optional[str] = None  # 繰り返し時刻 "HH:MM"
    created_at: str = ""
    channel: str = ""  # 通知先チャンネル

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class ReminderClient:
    """リマインダークライアント

    APSchedulerを使用してリマインダーをスケジュール・実行します。
    """

    def __init__(
        self,
        scheduler: AsyncIOScheduler,
        notification_callback: Optional[Callable] = None,
        timezone: str = "Asia/Tokyo",
        data_dir: str = "data",
    ):
        """初期化

        Args:
            scheduler: APSchedulerのインスタンス
            notification_callback: 通知時に呼び出すコールバック関数
            timezone: タイムゾーン
            data_dir: データ保存ディレクトリ
        """
        self.scheduler = scheduler
        self.notification_callback = notification_callback
        self.timezone = ZoneInfo(timezone)
        self.data_dir = Path(data_dir)
        self.reminders_file = self.data_dir / "reminders.json"

        # データディレクトリを作成
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # リマインダーを読み込み
        self.reminders: dict[str, Reminder] = {}
        self._load_reminders()

        # 既存のリマインダーをスケジューラに登録
        self._schedule_all_reminders()

        logger.info(
            "Reminder client initialized",
            reminders_count=len(self.reminders),
        )

    def _load_reminders(self) -> None:
        """リマインダーをファイルから読み込み"""
        if self.reminders_file.exists():
            try:
                with open(self.reminders_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for reminder_data in data:
                        reminder = Reminder(**reminder_data)
                        self.reminders[reminder.id] = reminder
                logger.info(f"Loaded {len(self.reminders)} reminders from file")
            except Exception as e:
                logger.error(f"Failed to load reminders: {e}")
                self.reminders = {}

    def _save_reminders(self) -> None:
        """リマインダーをファイルに保存"""
        try:
            with open(self.reminders_file, "w", encoding="utf-8") as f:
                data = [asdict(r) for r in self.reminders.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.reminders)} reminders to file")
        except Exception as e:
            logger.error(f"Failed to save reminders: {e}")

    def _schedule_all_reminders(self) -> None:
        """全リマインダーをスケジューラに登録"""
        for reminder in self.reminders.values():
            self._schedule_reminder(reminder)

    def _schedule_reminder(self, reminder: Reminder) -> None:
        """単一リマインダーをスケジューラに登録"""
        job_id = f"reminder_{reminder.id}"

        # 既存のジョブがあれば削除
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        try:
            if reminder.repeat == "daily":
                # 毎日リマインダー
                hour, minute = map(int, reminder.repeat_time.split(":"))
                trigger = CronTrigger(hour=hour, minute=minute, timezone=self.timezone)
            elif reminder.repeat == "weekly":
                # 毎週リマインダー
                hour, minute = map(int, reminder.repeat_time.split(":"))
                day_map = {
                    "mon": 0,
                    "tue": 1,
                    "wed": 2,
                    "thu": 3,
                    "fri": 4,
                    "sat": 5,
                    "sun": 6,
                }
                day_of_week = day_map.get(reminder.repeat_day.lower(), 0)
                trigger = CronTrigger(
                    day_of_week=day_of_week,
                    hour=hour,
                    minute=minute,
                    timezone=self.timezone,
                )
            elif reminder.repeat == "monthly":
                # 毎月リマインダー
                hour, minute = map(int, reminder.repeat_time.split(":"))
                trigger_time = datetime.fromisoformat(reminder.trigger_time)
                trigger = CronTrigger(
                    day=trigger_time.day,
                    hour=hour,
                    minute=minute,
                    timezone=self.timezone,
                )
            else:
                # 一度のみのリマインダー
                trigger_time = datetime.fromisoformat(reminder.trigger_time)
                if trigger_time.tzinfo is None:
                    trigger_time = trigger_time.replace(tzinfo=self.timezone)

                # 過去の時刻はスキップ
                if trigger_time <= datetime.now(self.timezone):
                    logger.info(f"Skipping past reminder: {reminder.id}")
                    return

                trigger = DateTrigger(run_date=trigger_time)

            self.scheduler.add_job(
                self._execute_reminder,
                trigger=trigger,
                args=[reminder.id],
                id=job_id,
                replace_existing=True,
            )
            logger.info(f"Scheduled reminder: {reminder.id}", message=reminder.message)

        except Exception as e:
            logger.error(f"Failed to schedule reminder {reminder.id}: {e}")

    async def _execute_reminder(self, reminder_id: str) -> None:
        """リマインダーを実行"""
        reminder = self.reminders.get(reminder_id)
        if not reminder:
            logger.warning(f"Reminder not found: {reminder_id}")
            return

        logger.info(f"Executing reminder: {reminder_id}", message=reminder.message)

        # コールバックを呼び出し
        if self.notification_callback:
            try:
                await self.notification_callback(
                    message=reminder.message,
                    channel=reminder.channel,
                )
            except Exception as e:
                logger.error(f"Reminder callback failed: {e}")

        # 一度のみのリマインダーは削除
        if not reminder.repeat:
            await self.delete_reminder(reminder_id)

    def set_notification_callback(self, callback: Callable) -> None:
        """通知コールバックを設定"""
        self.notification_callback = callback
        logger.info("Notification callback set")

    async def add_reminder(
        self,
        message: str,
        trigger_time: datetime,
        repeat: Optional[str] = None,
        repeat_day: Optional[str] = None,
        channel: str = "",
    ) -> Reminder:
        """リマインダーを追加

        Args:
            message: リマインダーメッセージ
            trigger_time: 発火時刻
            repeat: 繰り返し設定（"daily", "weekly", "monthly", None）
            repeat_day: 曜日（weekly用）
            channel: 通知先チャンネル

        Returns:
            作成されたReminder
        """
        reminder_id = str(uuid.uuid4())[:8]

        # タイムゾーン設定
        if trigger_time.tzinfo is None:
            trigger_time = trigger_time.replace(tzinfo=self.timezone)

        reminder = Reminder(
            id=reminder_id,
            message=message,
            trigger_time=trigger_time.isoformat(),
            repeat=repeat,
            repeat_day=repeat_day,
            repeat_time=trigger_time.strftime("%H:%M") if repeat else None,
            channel=channel,
        )

        self.reminders[reminder_id] = reminder
        self._save_reminders()
        self._schedule_reminder(reminder)

        logger.info(
            "Reminder added",
            id=reminder_id,
            message=message,
            trigger_time=trigger_time.isoformat(),
        )

        return reminder

    async def delete_reminder(self, reminder_id: str) -> bool:
        """リマインダーを削除

        Args:
            reminder_id: リマインダーID

        Returns:
            削除成功したかどうか
        """
        if reminder_id not in self.reminders:
            return False

        # スケジューラから削除
        job_id = f"reminder_{reminder_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        # メモリから削除
        del self.reminders[reminder_id]
        self._save_reminders()

        logger.info(f"Reminder deleted: {reminder_id}")
        return True

    def list_reminders(self) -> list[Reminder]:
        """全リマインダーを取得

        Returns:
            リマインダーリスト
        """
        return list(self.reminders.values())

    def get_reminder(self, reminder_id: str) -> Optional[Reminder]:
        """特定のリマインダーを取得

        Args:
            reminder_id: リマインダーID

        Returns:
            Reminderまたはなければ
        """
        return self.reminders.get(reminder_id)

    def format_reminder(self, reminder: Reminder) -> str:
        """リマインダーを読みやすい形式でフォーマット"""
        trigger_time = datetime.fromisoformat(reminder.trigger_time)

        if reminder.repeat == "daily":
            schedule = f"毎日 {reminder.repeat_time}"
        elif reminder.repeat == "weekly":
            day_names = {
                "mon": "月曜",
                "tue": "火曜",
                "wed": "水曜",
                "thu": "木曜",
                "fri": "金曜",
                "sat": "土曜",
                "sun": "日曜",
            }
            day_name = day_names.get(reminder.repeat_day.lower(), reminder.repeat_day)
            schedule = f"毎週{day_name} {reminder.repeat_time}"
        elif reminder.repeat == "monthly":
            schedule = f"毎月{trigger_time.day}日 {reminder.repeat_time}"
        else:
            schedule = trigger_time.strftime("%Y年%m月%d日 %H:%M")

        return f"[{reminder.id}] {reminder.message} ({schedule})"

    def format_all_reminders(self) -> str:
        """全リマインダーを読みやすい形式でフォーマット"""
        reminders = self.list_reminders()
        if not reminders:
            return "現在設定されているリマインダーはございません。"

        lines = ["【設定中のリマインダー】"]
        for reminder in reminders:
            lines.append(f"- {self.format_reminder(reminder)}")

        return "\n".join(lines)
