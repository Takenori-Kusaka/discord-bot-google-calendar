"""
Discord bot application that utilizes Google Calendar API and Gemini AI
for managing calendar events and providing intelligent responses.
"""

import os
import sys
import json
import datetime
import logging
from google.api_core import exceptions as google_exceptions
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
import discord
from dotenv import load_dotenv

# .env ファイルから環境変数を読み込む
load_dotenv()

# ロガーの設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 環境変数を取得
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
DISCORD_SERVER_ID = int(os.getenv("DISCORD_SERVER_ID"))

# Google Calendar API の設定
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS = None

if GOOGLE_SERVICE_ACCOUNT_JSON:
    logger.info("Using Google Service Account JSON from environment variable.")
    CREDENTIALS = service_account.Credentials.from_service_account_info(
        json.loads(GOOGLE_SERVICE_ACCOUNT_JSON), scopes=SCOPES
    )
else:
    logger.error("Error: GOOGLE_SERVICE_ACCOUNT_FILE environment variable not set.")
    sys.exit(1)


def get_calendar_service():
    """Google Calendar APIのサービスオブジェクトを取得します。"""
    try:
        service: Resource = build("calendar", "v3", credentials=CREDENTIALS)
        logger.info("Successfully built the Calendar API client.")
        return service
    except (ConnectionError, google_exceptions.GoogleAPIError) as e:
        logger.error("An error occurred while building the Calendar API client: %s", e)
        sys.exit(1)


def fetch_events(service, start_date, end_date):
    """指定された期間のGoogleカレンダーイベントを取得します。"""
    try:
        events_result = (
            service.events()
            .list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=start_date.isoformat() + "T00:00:00Z",
                timeMax=end_date.isoformat() + "T23:59:59Z",
                maxResults=100,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        logger.info("Successfully fetched %d events from Google Calendar.", len(events))
        # logger.debug("Events: %s", events)
        return events
    except (ConnectionError, google_exceptions.GoogleAPIError) as e:
        logger.error(
            "An error occurred while fetching events from Google Calendar: %s", e
        )
        return []


def is_same_event(discord_event, calendar_event, start_time, end_time):
    """DiscordイベントとGoogleカレンダーイベントが実質的に同じかチェックします。"""
    # イベント名が一致するかチェック
    if discord_event.name != calendar_event["summary"]:
        return False

    # Discord側のイベント時間をUTC→JSTに変換
    jst = datetime.timezone(datetime.timedelta(hours=9))
    discord_start = discord_event.start_time.astimezone(jst)
    discord_end = discord_event.end_time.astimezone(jst)

    # 開始日と終了日が一致するかチェック
    calendar_start = start_time.astimezone(jst)
    calendar_end = end_time.astimezone(jst)

    return (
        discord_start.date() == calendar_start.date()
        and discord_end.date() == calendar_end.date()
    )


def is_future_event(discord_event, now):
    """イベントが未来の日付かどうかをチェックします。"""
    return discord_event.start_time > now


class CreateEventsBot(discord.Client):
    """Discord bot class for sending schedule notifications."""

    def __init__(self, calendar_service, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calendar_service = calendar_service

    async def on_ready(self):
        """Discordのスケジュールイベントを作成します。"""
        logger.info("Logged in as %s", self.user)
        guild = self.get_guild(DISCORD_SERVER_ID)

        try:
            # UTCからJSTに変更
            jst = datetime.timezone(datetime.timedelta(hours=9))
            now = datetime.datetime.now(jst)
            # 1ヶ月分のイベントを取得（開始日を現在時刻に設定）
            start_date = now
            end_date = start_date + datetime.timedelta(days=30)
            calendar_events = fetch_events(
                self.calendar_service, start_date.date(), end_date.date()
            )

            # 既存のDiscordイベントを取得
            existing_events = await guild.fetch_scheduled_events()
            created_count = 0
            deleted_count = 0

            # 既存のDiscordイベントをチェックし、Googleカレンダーに存在しないものを削除
            for discord_event in existing_events:
                # 未来のイベントのみを処理
                if not is_future_event(discord_event, now):
                    await discord_event.delete()
                    deleted_count += 1
                    logger.info(f"Deleted past event: {discord_event.name}")
                    continue

                # Googleカレンダーに存在するかチェック
                exists_in_calendar = False
                for calendar_event in calendar_events:
                    if "T" not in calendar_event["start"].get("dateTime", calendar_event["start"].get("date")):
                        start_date = datetime.datetime.strptime(
                            calendar_event["start"].get("date"), "%Y-%m-%d"
                        )
                        start_time = start_date.replace(hour=6, tzinfo=jst)
                        end_time = start_date.replace(hour=21, tzinfo=jst)
                    else:
                        start_time = datetime.datetime.fromisoformat(
                            calendar_event["start"].get("dateTime")
                        )
                        end_time = datetime.datetime.fromisoformat(
                            calendar_event["end"].get("dateTime")
                        )

                    if is_same_event(discord_event, calendar_event, start_time, end_time):
                        exists_in_calendar = True
                        break

                if not exists_in_calendar:
                    await discord_event.delete()
                    deleted_count += 1
                    logger.info(f"Deleted event not in calendar: {discord_event.name}")

            # 新しいイベントの作成（既存のコード）
            for event in calendar_events:
                try:
                    # イベントデータの整形
                    event_data = {
                        "name": event["summary"][:100],  # イベント名を100文字に制限
                        "description": (
                            event.get("description", "") or "No description"
                        )[
                            :1000
                        ],  # 説明を1000文字に制限
                        "location": event.get(
                            "location", "未設定"
                        ),  # locationが空の場合はデフォルト値
                        "start": event["start"].get(
                            "dateTime", event["start"].get("date")
                        ),
                        "end": event["end"].get("dateTime", event["end"].get("date")),
                    }

                    # 終日イベントの処理
                    if "T" not in event_data["start"]:
                        jst = datetime.timezone(datetime.timedelta(hours=9))
                        start_date = datetime.datetime.strptime(
                            event_data["start"], "%Y-%m-%d"
                        )
                        start_time = start_date.replace(hour=6, tzinfo=jst)
                        end_time = start_date.replace(hour=21, tzinfo=jst)
                    else:
                        start_time = datetime.datetime.fromisoformat(
                            event_data["start"]
                        )
                        end_time = datetime.datetime.fromisoformat(event_data["end"])

                    # 過去のイベントをスキップ
                    if start_time < now:
                        logger.info(
                            "Event '%s' is in the past, skipping...", event_data["name"]
                        )
                        continue

                    # 重複チェック
                    is_duplicate = any(
                        is_same_event(discord_event, event, start_time, end_time)
                        for discord_event in existing_events
                    )

                    if is_duplicate:
                        logger.info(
                            "Event '%s' on %s already exists, skipping...",
                            event_data["name"],
                            start_time.date(),
                        )
                        continue

                    # Discordイベントを作成
                    await guild.create_scheduled_event(
                        name=event_data["name"],
                        description=event_data["description"],
                        start_time=start_time,
                        end_time=end_time,
                        location=event_data["location"],
                        privacy_level=discord.PrivacyLevel.guild_only,
                        entity_type=discord.EntityType.external,
                    )
                    created_count += 1
                    logger.info(
                        "Created Discord event: %s on %s",
                        event_data["name"],
                        start_time.date(),
                    )

                except (ValueError, KeyError) as e:
                    logger.error(
                        "Error creating event %s: %s",
                        event.get("summary", "Unknown"),
                        str(e),
                    )

            logger.info(f"Created {created_count} events and deleted {deleted_count} events")
            await self.close()
            return created_count

        except Exception as e:
            logger.error("Failed to process events: %s", str(e))
            await self.close()
            return 0


def main():
    """メイン関数"""
    try:
        service = get_calendar_service()
        intents = discord.Intents.default()
        bot = CreateEventsBot(calendar_service=service, intents=intents)
        bot.run(DISCORD_TOKEN)

    except (discord.LoginFailure, discord.ConnectionClosed) as e:
        logger.error("Discord connection error: %s", str(e))
        sys.exit(1)
    except Exception as e:
        logger.error("An unexpected error occurred: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
