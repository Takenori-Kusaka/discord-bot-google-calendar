"""朝の通知機能テスト"""
import asyncio
import sys
from dotenv import load_dotenv

load_dotenv()

from src.butler import Butler
from src.clients.calendar import GoogleCalendarClient
from src.clients.claude import ClaudeClient
from src.clients.discord import DiscordClient
from src.clients.weather import WeatherClient
from src.clients.today_info import TodayInfoClient
from src.clients.life_info import LifeInfoClient
from src.config.settings import get_settings
from src.utils.logger import setup_logger, get_logger


async def test_calendar():
    """カレンダーのみテスト"""
    print("=== Calendar Test ===", flush=True)

    settings = get_settings()
    setup_logger(log_level="DEBUG", log_dir=settings.log_dir)

    calendar_client = GoogleCalendarClient(
        calendar_id=settings.google_calendar_id,
        credentials_path=settings.google_credentials_path,
        timezone=settings.timezone,
    )

    print(f"Calendar ID: {settings.google_calendar_id}", flush=True)

    events = await calendar_client.get_today_events()
    print(f"Found {len(events)} events for today:", flush=True)
    for e in events:
        time_str = e.start.strftime("%H:%M") if not e.all_day else "終日"
        print(f"  - {time_str}: {e.summary}", flush=True)

    return events


async def test_morning_notification():
    """朝の通知をDiscordに送信"""
    print("=== Morning Notification Test ===", flush=True)

    settings = get_settings()
    setup_logger(log_level="DEBUG", log_dir=settings.log_dir)
    logger = get_logger(__name__)

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

    weather_client = WeatherClient(timezone=settings.timezone)
    today_info_client = TodayInfoClient(timezone=settings.timezone)
    life_info_client = LifeInfoClient(timezone=settings.timezone)

    butler = Butler(
        settings=settings,
        calendar_client=calendar_client,
        claude_client=claude_client,
        discord_client=discord_client,
        event_search_client=None,
        weather_client=weather_client,
        today_info_client=today_info_client,
        life_info_client=life_info_client,
        use_langgraph=settings.use_langgraph,
    )

    # Discord client needs to be connected
    print("Starting Discord client...", flush=True)

    async def run_discord():
        await discord_client.start()

    # Run in background
    task = asyncio.create_task(run_discord())
    print("Waiting for Discord connection...", flush=True)
    await asyncio.sleep(5)  # Wait for Discord connection

    print("Running morning notification...", flush=True)
    await butler.morning_notification()
    print("Morning notification completed!", flush=True)

    print("Closing Discord client...", flush=True)
    await discord_client.close()
    print("Done!", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "calendar":
        asyncio.run(test_calendar())
    else:
        asyncio.run(test_morning_notification())
