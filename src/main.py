"""メインエントリーポイント"""

import asyncio
import os
import signal
import sys

from dotenv import load_dotenv

# .envファイルをos.environに読み込む（LangChain等が環境変数を参照するため）
load_dotenv()

from .butler import Butler
from .clients.calendar import GoogleCalendarClient
from .clients.claude import ClaudeClient
from .clients.discord import DiscordClient
from .clients.event_search import EventSearchClient
from .clients.expense import ExpenseClient
from .clients.health import HealthClient
from .clients.home_assistant import HomeAssistantClient
from .clients.housework import HouseworkClient
from .clients.maps import GoogleMapsClient
from .clients.school import SchoolClient
from .clients.life_info import LifeInfoClient
from .clients.reminder import ReminderClient
from .clients.shopping_list import ShoppingListClient
from .clients.today_info import TodayInfoClient
from .clients.weather import WeatherClient
from .clients.web_search import WebSearchClient
from .config.settings import get_settings
from .scheduler.jobs import create_scheduler, setup_scheduler
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

    # イベント検索クライアント初期化（API設定がある場合のみ）
    event_search_client = None
    if settings.google_search_api_key and settings.google_search_engine_id:
        event_search_client = EventSearchClient(
            google_api_key=settings.google_search_api_key,
            google_search_engine_id=settings.google_search_engine_id,
            perplexity_api_key=settings.perplexity_api_key,
            timezone=settings.timezone,
        )
        logger.info("Event search client initialized")
    else:
        logger.info("Event search client not configured (missing API keys)")

    # 天気クライアント初期化
    weather_client = WeatherClient(timezone=settings.timezone)
    logger.info("Weather client initialized")

    # 今日は何の日クライアント初期化
    today_info_client = TodayInfoClient(
        timezone=settings.timezone,
        perplexity_api_key=settings.perplexity_api_key,
    )
    logger.info("TodayInfo client initialized")

    # 生活影響情報クライアント初期化
    life_info_client = LifeInfoClient(timezone=settings.timezone)
    logger.info("LifeInfo client initialized")

    # Web検索クライアント初期化（Perplexity API設定がある場合のみ）
    web_search_client = None
    if settings.perplexity_api_key:
        web_search_client = WebSearchClient(
            perplexity_api_key=settings.perplexity_api_key,
        )
        logger.info("Web search client initialized")
    else:
        logger.info("Web search client not configured (missing Perplexity API key)")

    # スケジューラを先に作成（リマインダークライアントで使用）
    scheduler = create_scheduler(timezone=settings.timezone)

    # リマインダークライアント初期化
    reminder_client = ReminderClient(
        scheduler=scheduler,
        timezone=settings.timezone,
    )
    logger.info("Reminder client initialized")

    # 買い物リストクライアント初期化
    shopping_list_client = ShoppingListClient()
    logger.info("Shopping list client initialized")

    # 家事記録クライアント初期化
    housework_client = HouseworkClient()
    logger.info("Housework client initialized")

    # Home Assistantクライアント初期化（トークンが設定されている場合のみ）
    home_assistant_client = None
    if os.environ.get("HOME_ASSISTANT_TOKEN"):
        home_assistant_client = HomeAssistantClient()
        logger.info("Home Assistant client initialized")
    else:
        logger.info("Home Assistant client not configured (missing token)")

    # 家計簿クライアント初期化
    expense_client = ExpenseClient()
    logger.info("Expense client initialized")

    # 学校情報クライアント初期化
    school_client = SchoolClient()
    logger.info("School client initialized")

    # 健康記録クライアント初期化
    health_client = HealthClient()
    logger.info("Health client initialized")

    # Google Mapsクライアント初期化（APIキーが設定されている場合のみ）
    maps_client = None
    if settings.google_maps_api_key:
        maps_client = GoogleMapsClient(
            api_key=settings.google_maps_api_key,
            home_address=settings.home_address,
            timezone=settings.timezone,
        )
        logger.info("Google Maps client initialized")
    else:
        logger.info("Google Maps client not configured (missing API key)")

    # Butler初期化
    butler = Butler(
        settings=settings,
        calendar_client=calendar_client,
        claude_client=claude_client,
        discord_client=discord_client,
        event_search_client=event_search_client,
        weather_client=weather_client,
        today_info_client=today_info_client,
        life_info_client=life_info_client,
        web_search_client=web_search_client,
        reminder_client=reminder_client,
        shopping_list_client=shopping_list_client,
        housework_client=housework_client,
        home_assistant_client=home_assistant_client,
        expense_client=expense_client,
        school_client=school_client,
        health_client=health_client,
        maps_client=maps_client,
        use_langgraph=settings.use_langgraph,
    )

    # リマインダー通知コールバックを設定（Discordに通知）
    async def reminder_notification_callback(message: str, channel: str):
        """リマインダー通知をDiscordに送信"""
        butler_message = (
            f"旦那様、執事の{butler.name}でございます。\n"
            f"リマインダーをお知らせいたします。\n\n"
            f"📋 {message}"
        )
        # チャンネルが指定されていない場合は予定チャンネルに送信
        target_channel = channel or settings.discord_channel_schedule
        await discord_client.send_to_channel(target_channel, butler_message)

    reminder_client.set_notification_callback(reminder_notification_callback)

    # スケジューラにジョブを追加（Butlerのメソッドを使用）
    setup_scheduler(
        morning_job=butler.morning_notification,
        morning_hour=settings.morning_notification_hour,
        morning_minute=settings.morning_notification_minute,
        weekly_job=butler.weekly_event_notification if event_search_client else None,
        weekly_day=settings.weekly_event_day,
        weekly_hour=settings.weekly_event_hour,
        life_info_job=butler.weekly_life_info_notification,
        life_info_day=getattr(settings, "life_info_day", "mon"),
        life_info_hour=getattr(settings, "life_info_hour", 9),
        coaching_job=butler.daily_coaching_notification,
        coaching_hour=settings.coaching_notification_hour,
        coaching_minute=settings.coaching_notification_minute,
        timezone=settings.timezone,
        scheduler=scheduler,
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
