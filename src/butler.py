"""Butler Core - 執事「黒田」のコアロジック"""

from pathlib import Path

import yaml

from .clients.calendar import CalendarEvent, GoogleCalendarClient
from .clients.claude import ClaudeClient
from .clients.discord import DiscordClient
from .config.settings import Settings
from .utils.logger import get_logger

logger = get_logger(__name__)


class Butler:
    """執事「黒田」"""

    def __init__(
        self,
        settings: Settings,
        calendar_client: GoogleCalendarClient,
        claude_client: ClaudeClient,
        discord_client: DiscordClient,
    ):
        """初期化

        Args:
            settings: アプリケーション設定
            calendar_client: Google Calendarクライアント
            claude_client: Claudeクライアント
            discord_client: Discordクライアント
        """
        self.settings = settings
        self.calendar = calendar_client
        self.claude = claude_client
        self.discord = discord_client
        self.name = settings.butler_name

        # フィルタリングルールを読み込み
        self.ignore_patterns = self._load_rules("config/ignore_rules.yml")
        self.notify_patterns = self._load_rules("config/notify_rules.yml")

        logger.info(f"執事「{self.name}」、準備完了でございます。")

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

            # 3. 執事口調のメッセージを生成
            message = await self.claude.generate_butler_message(
                important_events,
                butler_name=self.name,
            )

            # 4. Discordに送信
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

    async def handle_message(self, message: str) -> str:
        """Discordメッセージを処理（Phase 3）

        Args:
            message: 受信したメッセージ

        Returns:
            str: 応答メッセージ
        """
        # Phase 3で実装
        return f"かしこまりました。ただいま「{message}」についてお調べいたします。"
