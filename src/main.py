"""メインエントリーポイント"""

import asyncio
import signal
import sys

from .butler import Butler
from .clients.calendar import GoogleCalendarClient
from .clients.claude import ClaudeClient
from .clients.discord import DiscordClient
from .config.settings import get_settings
from .scheduler.jobs import setup_scheduler
from .utils.logger import get_logger, setup_logger

logger = get_logger(__name__)


async def main():
    """メイン処理"""
    # 設定読み込み
    settings = get_settings()

    # ログ設定
    setup_logger(
        log_level=settings.log_level,
        log_dir=settings.log_dir,
    )

    logger.info("=== 執事「黒田」起動中 ===")

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

    # スケジューラ設定
    scheduler = setup_scheduler(
        morning_job=butler.morning_notification,
        morning_hour=settings.morning_notification_hour,
        morning_minute=settings.morning_notification_minute,
        timezone=settings.timezone,
    )

    # シグナルハンドラ設定
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(shutdown(scheduler, discord_client)),
            )
        except NotImplementedError:
            # Windowsではadd_signal_handlerがサポートされていない
            pass

    try:
        # スケジューラ開始
        scheduler.start()
        logger.info("Scheduler started")

        # Discord Bot開始
        logger.info("Starting Discord bot...")
        await discord_client.start()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error("Unexpected error", error=str(e))
    finally:
        await shutdown(scheduler, discord_client)


async def shutdown(scheduler, discord_client):
    """シャットダウン処理"""
    logger.info("Shutting down...")

    # スケジューラ停止
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    # Discord Bot停止
    await discord_client.close()
    logger.info("Discord bot stopped")

    logger.info("=== 執事「黒田」、本日の勤務を終了いたします ===")


def run():
    """エントリーポイント"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    run()
