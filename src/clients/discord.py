"""Discord クライアント"""

import base64
import io
from typing import Callable, Optional

import aiohttp
import discord
from discord.ext import commands
from PIL import Image

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

        # メッセージハンドラ（Butlerから設定）
        self._message_handler: Optional[Callable] = None

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

    def set_message_handler(self, handler: Callable) -> None:
        """メッセージハンドラを設定

        Args:
            handler: メッセージ処理関数 (message: str, channel: str, images: list) -> str
        """
        self._message_handler = handler
        logger.info("Message handler registered")

    def _resize_image_for_api(
        self, image_data: bytes, max_size_bytes: int = 4_500_000
    ) -> bytes:
        """画像をAPI制限内にリサイズする

        Anthropic APIの制限は5MB。安全マージンを取って4.5MBを上限とする。

        Args:
            image_data: 元の画像データ
            max_size_bytes: 最大サイズ（バイト）

        Returns:
            bytes: リサイズ後の画像データ
        """
        # 既にサイズが小さければそのまま返す
        if len(image_data) <= max_size_bytes:
            return image_data

        logger.info(f"Image size {len(image_data)} bytes exceeds limit, resizing...")

        try:
            # 画像を開く
            img = Image.open(io.BytesIO(image_data))
            original_format = img.format or "PNG"

            # RGBAの場合はRGBに変換（JPEG保存用）
            if img.mode == "RGBA":
                # 白背景でアルファチャンネルを合成
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # 縮小率を計算して段階的にリサイズ
            quality = 85
            scale = 1.0

            while True:
                # リサイズ
                if scale < 1.0:
                    new_size = (int(img.width * scale), int(img.height * scale))
                    resized = img.resize(new_size, Image.Resampling.LANCZOS)
                else:
                    resized = img

                # JPEG形式で保存
                output = io.BytesIO()
                resized.save(output, format="JPEG", quality=quality, optimize=True)
                result = output.getvalue()

                logger.info(
                    f"Resized image: scale={scale:.2f}, quality={quality}, size={len(result)} bytes"
                )

                if len(result) <= max_size_bytes:
                    return result

                # 次の試行：まず品質を下げ、それでもダメならスケールを下げる
                if quality > 60:
                    quality -= 10
                elif scale > 0.3:
                    scale -= 0.1
                    quality = 85  # スケールを下げたら品質をリセット
                else:
                    # これ以上縮小できない場合はそのまま返す
                    logger.warning(
                        f"Could not reduce image below limit, returning {len(result)} bytes"
                    )
                    return result

        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            return image_data

    async def _download_image_as_base64(
        self, url: str
    ) -> tuple[str | None, str | None]:
        """画像をダウンロードしてbase64エンコードする

        Args:
            url: 画像URL

        Returns:
            tuple[str | None, str | None]: (base64エンコードされた画像データ, メディアタイプ)
        """
        logger.info(f"Attempting to download image from URL: {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    logger.info(f"Image download response status: {response.status}")
                    if response.status == 200:
                        data = await response.read()
                        original_size = len(data)

                        # APIサイズ制限チェック・リサイズ
                        resized_data = self._resize_image_for_api(data)

                        # リサイズした場合はメディアタイプをJPEGに変更
                        if len(resized_data) != original_size:
                            media_type = "image/jpeg"
                        else:
                            media_type = None  # 呼び出し元で決定

                        base64_data = base64.b64encode(resized_data).decode("utf-8")
                        logger.info(
                            f"Image processed: original={original_size}, final={len(resized_data)}, base64={len(base64_data)}"
                        )
                        return base64_data, media_type
                    else:
                        logger.warning(
                            f"Failed to download image: status={response.status}, url={url}"
                        )
                        return None, None
        except Exception as e:
            logger.error(f"Error downloading image: {e}, url={url}")
            return None, None

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
        async def on_message(message: discord.Message):
            # Bot自身のメッセージは無視
            if message.author == self.bot.user:
                return

            # 対象サーバーのメッセージのみ処理
            if message.guild and message.guild.id != self.guild_id:
                return

            # Botへのメンションまたは「黒田」を含むメッセージに反応
            bot_mentioned = self.bot.user in message.mentions
            butler_called = "黒田" in message.content

            if not (bot_mentioned or butler_called):
                return

            # メッセージハンドラが設定されていない場合
            if not self._message_handler:
                logger.warning("Message handler not set")
                return

            try:
                # メンションを除去してメッセージを取得
                content = message.content
                if self.bot.user:
                    content = content.replace(f"<@{self.bot.user.id}>", "").strip()
                content = content.replace("黒田", "").strip()

                # 画像添付をチェック
                logger.info(f"Message has {len(message.attachments)} attachments")
                images = []
                image_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp")
                for attachment in message.attachments:
                    logger.info(
                        f"Checking attachment: filename={attachment.filename}, url={attachment.url}, content_type={attachment.content_type}"
                    )
                    if attachment.filename.lower().endswith(image_extensions):
                        logger.info(f"Downloading image: {attachment.filename}")
                        image_data, resized_media_type = (
                            await self._download_image_as_base64(attachment.url)
                        )
                        if image_data:
                            # リサイズした場合はJPEG、そうでなければ拡張子から判定
                            if resized_media_type:
                                media_type = resized_media_type
                            else:
                                ext = attachment.filename.lower().split(".")[-1]
                                media_type = (
                                    f"image/{ext}" if ext != "jpg" else "image/jpeg"
                                )
                            images.append(
                                {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                }
                            )
                            logger.info(
                                f"Image attachment processed: {attachment.filename}, media_type={media_type}"
                            )
                        else:
                            logger.warning(
                                f"Failed to download image: {attachment.filename}"
                            )
                    else:
                        logger.info(
                            f"Skipping non-image attachment: {attachment.filename}"
                        )

                logger.info(f"Total images processed: {len(images)}")

                if not content and not images:
                    content = "何かお手伝いできることはございますか？"
                elif not content and images:
                    content = "この画像について教えてください"

                logger.info(
                    "Processing message",
                    author=str(message.author),
                    channel=(
                        message.channel.name
                        if hasattr(message.channel, "name")
                        else "DM"
                    ),
                    content_length=len(content),
                    image_count=len(images),
                )

                # Butlerで処理
                channel_name = (
                    message.channel.name if hasattr(message.channel, "name") else "dm"
                )
                response = await self._message_handler(content, channel_name, images)

                # 応答を送信
                await message.reply(response)

            except Exception as e:
                logger.error("Error handling message", error=str(e))
                await message.reply(
                    "恐れ入ります、処理中にエラーが発生いたしました。"
                    "しばらくしてから再度お試しくださいませ。"
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

    async def is_duplicate_message(
        self, channel_name: str, message: str, limit: int = 3
    ) -> bool:
        """直近メッセージとの重複判定

        Args:
            channel_name: チャンネル名
            message: 比較するメッセージ
            limit: 直近取得件数

        Returns:
            bool: 重複している場合True
        """
        channel = self.get_channel_by_name(channel_name)
        if not channel:
            return False

        try:
            async for msg in channel.history(limit=limit):
                if (
                    msg.author == self.bot.user
                    and msg.content.strip() == message.strip()
                ):
                    return True
        except Exception as e:
            logger.warning("Failed to check channel history", error=str(e))

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
