"""Discord クライアント"""

import discord
from discord.ext import commands

from ..utils.logger import get_logger

logger = get_logger(__name__)


class DiscordClient:
    """Discord Bot クライアント"""

    def __init__(
        self,
        token: str,
        guild_id: int,
        owner_id: int,
    ):
        """初期化

        Args:
            token: Discord Botトークン
            guild_id: サーバーID
            owner_id: オーナーのユーザーID
        """
        self.token = token
        self.guild_id = guild_id
        self.owner_id = owner_id

        # Botインスタンス作成
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        self.bot = commands.Bot(
            command_prefix="!",
            intents=intents,
        )

        self._setup_events()
        logger.info("Discord client initialized", guild_id=guild_id)

    def _setup_events(self):
        """イベントハンドラを設定"""

        @self.bot.event
        async def on_ready():
            logger.info(
                "Discord bot connected",
                user=str(self.bot.user),
                guilds=len(self.bot.guilds),
            )

        @self.bot.event
        async def on_error(event, *args, **kwargs):
            logger.error("Discord error", event=event)

    async def start(self):
        """Botを起動"""
        await self.bot.start(self.token)

    async def close(self):
        """Botを停止"""
        await self.bot.close()

    def get_guild(self) -> discord.Guild | None:
        """サーバーを取得"""
        return self.bot.get_guild(self.guild_id)

    def get_channel_by_name(self, name: str) -> discord.TextChannel | None:
        """チャンネル名からチャンネルを取得

        Args:
            name: チャンネル名

        Returns:
            discord.TextChannel | None: チャンネル
        """
        guild = self.get_guild()
        if not guild:
            logger.warning("Guild not found", guild_id=self.guild_id)
            return None

        for channel in guild.text_channels:
            if channel.name == name:
                return channel

        logger.warning("Channel not found", name=name)
        return None

    async def send_to_channel(self, channel_name: str, message: str) -> bool:
        """チャンネルにメッセージを送信

        Args:
            channel_name: チャンネル名
            message: メッセージ

        Returns:
            bool: 送信成功したかどうか
        """
        channel = self.get_channel_by_name(channel_name)
        if not channel:
            return False

        try:
            await channel.send(message)
            logger.info(
                "Message sent to channel",
                channel=channel_name,
                length=len(message),
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to send message",
                channel=channel_name,
                error=str(e),
            )
            return False

    async def send_dm_to_owner(self, message: str) -> bool:
        """オーナーにDMを送信（エラー通知用）

        Args:
            message: メッセージ

        Returns:
            bool: 送信成功したかどうか
        """
        try:
            user = await self.bot.fetch_user(self.owner_id)
            if user:
                await user.send(message)
                logger.info("DM sent to owner", length=len(message))
                return True
            return False
        except Exception as e:
            logger.error("Failed to send DM", error=str(e))
            return False

    async def send_error_notification(
        self, error: Exception, context: str = ""
    ) -> bool:
        """エラー通知をDMで送信

        Args:
            error: エラー
            context: エラーが発生したコンテキスト

        Returns:
            bool: 送信成功したかどうか
        """
        message = f"""旦那様、恐れ入ります。執事からのご報告でございます。

システムにて問題が発生いたしました。

【発生箇所】
{context or "不明"}

【エラー内容】
{type(error).__name__}: {str(error)}

ご確認のほど、よろしくお願い申し上げます。"""

        return await self.send_dm_to_owner(message)
