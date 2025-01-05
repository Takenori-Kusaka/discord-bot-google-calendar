"""
Discord bot application that utilizes Google Calendar API and Gemini AI
for managing calendar events and providing intelligent responses.
"""

import os
import sys
import json
import datetime
import logging
import argparse
from google.api_core import exceptions as google_exceptions
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
import google.generativeai as genai
import discord
from dotenv import load_dotenv

# .env ファイルから環境変数を読み込む
load_dotenv()

# ロガーの設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 環境変数を取得
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
DISCORD_SERVER_ID = int(os.getenv("DISCORD_SERVER_ID"))

# Google AI Studioで発行したAPIキーを設定
genai.configure(api_key=GOOGLE_API_KEY)

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
        logger.debug("Events: %s", events)
        return events
    except (ConnectionError, google_exceptions.GoogleAPIError) as e:
        logger.error(
            "An error occurred while fetching events from Google Calendar: %s", e
        )
        return []


def filter_events(events, start_date, end_date):
    """指定された期間のイベントをフィルタリングします。"""
    filtered_events = []
    for event in events:
        start_str = event["start"].get("dateTime", event["start"].get("date"))
        logger.debug("Event start time: %s", start_str)

        if "T" in start_str:
            event_date = datetime.datetime.strptime(
                start_str, "%Y-%m-%dT%H:%M:%S%z"
            ).date()
        else:
            event_date = datetime.datetime.strptime(start_str, "%Y-%m-%d").date()

        if start_date <= event_date <= end_date:
            filtered_events.append(event)
            logger.debug("Added event for the period: %s", event)
    return filtered_events


def format_schedule_text(filtered_events, period_jp):
    """フィルタリングされたイベントをテキスト形式にフォーマットします。"""
    if not filtered_events:
        return f"{period_jp}の予定はありません。"
    schedule_text = f"{period_jp}の予定は以下の通りです。\n"
    for event in filtered_events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        summary = event["summary"]

        if "T" in start:
            start_datetime = datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
            start_date = start_datetime.strftime("%Y-%m-%d")
            start_time = start_datetime.strftime("%H:%M")
            event_end_time = (
                datetime.datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z").strftime("%H:%M")
                if "T" in end
                else "終日"
            )
            schedule_text += (
                f"- {start_date} {start_time}から{event_end_time}：{summary}\n"
            )
        else:
            start_date = datetime.datetime.strptime(start, "%Y-%m-%d").strftime(
                "%Y-%m-%d"
            )
            schedule_text += f"- {start_date} 終日：{summary}\n"
    logger.debug("Schedule text: %s", schedule_text)
    return schedule_text


def generate_response_text(schedule_text, period_jp):
    """スケジュールテキストを元にAI応答テキストを生成します。"""
    model = genai.GenerativeModel("gemini-pro")

    prompt = f"""
    あなたはGoogleカレンダーの情報をわかりやすく伝えるアシスタントAIです。
    以下の情報を元に、{period_jp}の予定をユーザーに通知してください。
    口調は丁寧に、簡潔かつ明瞭に伝えてください。
    必ず、以下の「{period_jp}の予定」から情報を取り出して箇条書きで文章を作成してください。

    {period_jp}の予定：
    {schedule_text}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except (ConnectionError, google_exceptions.GoogleAPIError) as e:
        logger.error("An error occurred: %s", e)
        return None


class ScheduleBot(discord.Client):
    """Discord bot class for sending schedule notifications."""
    def __init__(self, response_text: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response_text = response_text

    async def on_ready(self):
        """Called when the bot is ready to start sending messages."""
        logger.info("Logged in as %s", self.user)
        guild = self.get_guild(DISCORD_SERVER_ID)
        if guild:
            channel = guild.get_channel(DISCORD_CHANNEL_ID)
            if channel:
                await channel.send(self.response_text)
        await self.close()

def get_date_range(period: str, today: datetime.date) -> tuple[datetime.date, datetime.date]:
    """期間に応じた日付範囲を返します。"""
    if period == "today":
        return today, today
    elif period == "week":
        this_week_monday = today - datetime.timedelta(days=today.weekday())
        return this_week_monday, this_week_monday + datetime.timedelta(days=6)
    else:  # month
        start_date = today.replace(day=1)
        return start_date, (start_date.replace(month=start_date.month % 12 + 1, day=1) -
                          datetime.timedelta(days=1))

def main():
    """メイン関数。カレンダーサービスを取得し、イベントを取得して通知を生成します。"""
    service = get_calendar_service()
    today = datetime.datetime.utcnow().date()

    parser = argparse.ArgumentParser(description="Generate schedule notifications.")
    parser.add_argument(
        "--period",
        choices=["today", "week", "month"],
        default="today",
        help="Period of the schedule to generate.",
    )
    args = parser.parse_args()

    period_jp = {"today": "今日", "week": "今週", "month": "今月"}[args.period]
    start_date, end_date = get_date_range(args.period, today)

    logger.debug("Start date: %s, End date: %s", start_date, end_date)

    events = fetch_events(service, start_date, end_date)
    filtered_events = filter_events(events, start_date, end_date)
    schedule_text = format_schedule_text(filtered_events, period_jp)
    response_text = generate_response_text(schedule_text, period_jp)

    if response_text:
        logger.info(response_text)
        intents = discord.Intents.default()
        bot = ScheduleBot(response_text, intents=intents)
        bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
