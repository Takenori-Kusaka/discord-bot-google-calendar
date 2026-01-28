"""Discord クライアントの単体テスト"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord.ext import commands

from src.clients.discord import DiscordClient


class TestDiscordClient:
    """DiscordClientクラスのテスト"""

    @pytest.fixture
    def mock_bot(self):
        """Discord Botのモック"""
        bot = MagicMock(spec=commands.Bot)
        bot.user = MagicMock()
        bot.user.id = 123456789
        bot.guilds = []
        bot.get_guild = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock()
        bot.start = AsyncMock()
        bot.close = AsyncMock()
        return bot

    @pytest.fixture
    def discord_client(self, mock_bot):
        """DiscordClientのインスタンス（モック済み）"""
        with patch("src.clients.discord.commands.Bot") as mock_bot_class:
            mock_bot_class.return_value = mock_bot
            client = DiscordClient(
                token="test-token",
                guild_id=111111111,
                owner_id=222222222,
            )
            client.bot = mock_bot
            return client

    @pytest.fixture
    def mock_guild(self):
        """Guildのモック"""
        guild = MagicMock(spec=discord.Guild)
        guild.id = 111111111

        # テキストチャンネルを作成
        schedule_channel = MagicMock(spec=discord.TextChannel)
        schedule_channel.name = "予定"
        schedule_channel.send = AsyncMock()
        schedule_channel.history = MagicMock()

        region_channel = MagicMock(spec=discord.TextChannel)
        region_channel.name = "地域のこと"
        region_channel.send = AsyncMock()

        guild.text_channels = [schedule_channel, region_channel]
        return guild


class TestMessageHandler(TestDiscordClient):
    """メッセージハンドラのテスト"""

    def test_set_message_handler(self, discord_client):
        """メッセージハンドラの設定"""

        async def dummy_handler(message, channel, images):
            return "テスト応答"

        discord_client.set_message_handler(dummy_handler)

        assert discord_client._message_handler is not None


class TestGetGuild(TestDiscordClient):
    """get_guildメソッドのテスト"""

    def test_get_guild_found(self, discord_client, mock_bot, mock_guild):
        """Guildが見つかる場合"""
        mock_bot.get_guild.return_value = mock_guild

        result = discord_client.get_guild()

        assert result == mock_guild
        mock_bot.get_guild.assert_called_with(111111111)

    def test_get_guild_not_found(self, discord_client, mock_bot):
        """Guildが見つからない場合"""
        mock_bot.get_guild.return_value = None

        result = discord_client.get_guild()

        assert result is None


class TestGetChannelByName(TestDiscordClient):
    """get_channel_by_nameメソッドのテスト"""

    def test_get_channel_found(self, discord_client, mock_bot, mock_guild):
        """チャンネルが見つかる場合"""
        mock_bot.get_guild.return_value = mock_guild

        result = discord_client.get_channel_by_name("予定")

        assert result is not None
        assert result.name == "予定"

    def test_get_channel_not_found(self, discord_client, mock_bot, mock_guild):
        """チャンネルが見つからない場合"""
        mock_bot.get_guild.return_value = mock_guild

        result = discord_client.get_channel_by_name("存在しないチャンネル")

        assert result is None

    def test_get_channel_no_guild(self, discord_client, mock_bot):
        """Guildが見つからない場合"""
        mock_bot.get_guild.return_value = None

        result = discord_client.get_channel_by_name("予定")

        assert result is None


class TestSendToChannel(TestDiscordClient):
    """send_to_channelメソッドのテスト"""

    @pytest.mark.asyncio
    async def test_send_to_channel_success(self, discord_client, mock_bot, mock_guild):
        """メッセージ送信成功"""
        mock_bot.get_guild.return_value = mock_guild
        schedule_channel = mock_guild.text_channels[0]

        result = await discord_client.send_to_channel("予定", "テストメッセージ")

        assert result is True
        schedule_channel.send.assert_called_once_with("テストメッセージ")

    @pytest.mark.asyncio
    async def test_send_to_channel_no_channel(self, discord_client, mock_bot):
        """チャンネルが見つからない場合"""
        mock_bot.get_guild.return_value = None

        result = await discord_client.send_to_channel("予定", "テストメッセージ")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_to_channel_send_error(
        self, discord_client, mock_bot, mock_guild
    ):
        """送信エラーの場合"""
        mock_bot.get_guild.return_value = mock_guild
        schedule_channel = mock_guild.text_channels[0]
        schedule_channel.send.side_effect = discord.HTTPException(MagicMock(), "Error")

        result = await discord_client.send_to_channel("予定", "テストメッセージ")

        assert result is False
        schedule_channel.send.assert_called_once_with("テストメッセージ")


class TestSendDmToOwner(TestDiscordClient):
    """send_dm_to_ownerメソッドのテスト"""

    @pytest.mark.asyncio
    async def test_send_dm_success(self, discord_client, mock_bot):
        """DM送信成功"""
        mock_user = MagicMock()
        mock_user.send = AsyncMock()
        mock_bot.fetch_user.return_value = mock_user

        result = await discord_client.send_dm_to_owner("テストDM")

        assert result is True
        mock_user.send.assert_called_once_with("テストDM")

    @pytest.mark.asyncio
    async def test_send_dm_user_not_found(self, discord_client, mock_bot):
        """ユーザーが見つからない場合"""
        mock_bot.fetch_user.return_value = None

        result = await discord_client.send_dm_to_owner("テストDM")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_dm_error(self, discord_client, mock_bot):
        """DM送信エラー"""
        mock_bot.fetch_user.side_effect = Exception("Fetch Error")

        result = await discord_client.send_dm_to_owner("テストDM")

        assert result is False


class TestSendErrorNotification(TestDiscordClient):
    """send_error_notificationメソッドのテスト"""

    @pytest.mark.asyncio
    async def test_send_error_notification_success(self, discord_client, mock_bot):
        """エラー通知送信成功"""
        mock_user = MagicMock()
        mock_user.send = AsyncMock()
        mock_bot.fetch_user.return_value = mock_user

        error = ValueError("テストエラー")
        result = await discord_client.send_error_notification(
            error, context="朝の予定通知"
        )

        assert result is True
        # 送信されたメッセージを検証
        call_args = mock_user.send.call_args[0][0]
        assert "旦那様" in call_args
        assert "朝の予定通知" in call_args
        assert "ValueError" in call_args
        assert "テストエラー" in call_args

    @pytest.mark.asyncio
    async def test_send_error_notification_no_context(self, discord_client, mock_bot):
        """コンテキストなしのエラー通知"""
        mock_user = MagicMock()
        mock_user.send = AsyncMock()
        mock_bot.fetch_user.return_value = mock_user

        error = RuntimeError("ランタイムエラー")
        result = await discord_client.send_error_notification(error)

        assert result is True
        call_args = mock_user.send.call_args[0][0]
        assert "不明" in call_args


class TestIsDuplicateMessage(TestDiscordClient):
    """is_duplicate_messageメソッドのテスト"""

    @pytest.mark.asyncio
    async def test_is_duplicate_true(self, discord_client, mock_bot, mock_guild):
        """重複メッセージが見つかる場合"""
        mock_bot.get_guild.return_value = mock_guild
        schedule_channel = mock_guild.text_channels[0]

        # 履歴のモック
        mock_message = MagicMock()
        mock_message.author = mock_bot.user
        mock_message.content = "同じメッセージ"

        async def mock_history(limit):
            for msg in [mock_message]:
                yield msg

        schedule_channel.history = mock_history

        result = await discord_client.is_duplicate_message("予定", "同じメッセージ")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_duplicate_false(self, discord_client, mock_bot, mock_guild):
        """重複メッセージが見つからない場合"""
        mock_bot.get_guild.return_value = mock_guild
        schedule_channel = mock_guild.text_channels[0]

        # 履歴のモック（異なるメッセージ）
        mock_message = MagicMock()
        mock_message.author = mock_bot.user
        mock_message.content = "異なるメッセージ"

        async def mock_history(limit):
            for msg in [mock_message]:
                yield msg

        schedule_channel.history = mock_history

        result = await discord_client.is_duplicate_message("予定", "新しいメッセージ")

        assert result is False

    @pytest.mark.asyncio
    async def test_is_duplicate_no_channel(self, discord_client, mock_bot):
        """チャンネルが見つからない場合"""
        mock_bot.get_guild.return_value = None

        result = await discord_client.is_duplicate_message("予定", "メッセージ")

        assert result is False


class TestBotLifecycle(TestDiscordClient):
    """Bot起動・停止のテスト"""

    @pytest.mark.asyncio
    async def test_start(self, discord_client, mock_bot):
        """Bot起動"""
        await discord_client.start()

        mock_bot.start.assert_called_once_with("test-token")

    @pytest.mark.asyncio
    async def test_close(self, discord_client, mock_bot):
        """Bot停止"""
        await discord_client.close()

        mock_bot.close.assert_called_once()
