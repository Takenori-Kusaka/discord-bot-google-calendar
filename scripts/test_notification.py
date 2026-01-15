"""通知テストスクリプト"""

import asyncio
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.butler import Butler
from src.clients.calendar import GoogleCalendarClient
from src.clients.claude import ClaudeClient
from src.clients.discord import DiscordClient
from src.config.settings import get_settings
from src.utils.logger import setup_logger, get_logger


async def test_morning_notification():
    """朝の通知をテスト実行"""
    # 設定読み込み
    settings = get_settings()

    # ログ設定
    setup_logger(log_level="DEBUG", log_dir=settings.log_dir)
    logger = get_logger(__name__)

    logger.info("=== 通知テスト開始 ===")

    # クライアント初期化
    calendar_client = GoogleCalendarClient(
        calendar_id=settings.google_calendar_id,
        credentials_path=settings.google_credentials_path,
        timezone=settings.timezone,
    )

    claude_client = ClaudeClient(
        api_key=settings.anthropic_api_key,
        model=settings.claude_model,
    )

    discord_client = DiscordClient(
        token=settings.discord_bot_token,
        guild_id=settings.discord_guild_id,
        owner_id=settings.discord_owner_id,
    )

    # Butler初期化
    butler = Butler(
        settings=settings,
        calendar_client=calendar_client,
        claude_client=claude_client,
        discord_client=discord_client,
    )

    # テスト完了フラグ
    test_done = asyncio.Event()

    # on_readyイベントをオーバーライド
    original_on_ready = discord_client.bot.on_ready

    @discord_client.bot.event
    async def on_ready():
        """Bot準備完了時の処理"""
        await original_on_ready()
        logger.info("テスト実行開始...")

        try:
            # 少し待機
            await asyncio.sleep(2)

            # 朝の通知を実行
            logger.info("朝の通知を実行中...")
            await butler.morning_notification()
            logger.info("通知完了！Discordを確認してください")

        except Exception as e:
            logger.error(f"エラー発生: {e}")
        finally:
            # 終了
            await asyncio.sleep(3)
            test_done.set()
            await discord_client.close()

    # Discord Bot開始
    try:
        # タイムアウト付きで実行
        bot_task = asyncio.create_task(discord_client.start())
        done_task = asyncio.create_task(test_done.wait())

        # どちらかが完了するまで待機
        done, pending = await asyncio.wait(
            [bot_task, done_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # 残りのタスクをキャンセル
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Bot実行エラー: {e}")

    logger.info("=== 通知テスト終了 ===")


if __name__ == "__main__":
    asyncio.run(test_morning_notification())
