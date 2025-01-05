"""
Discord bot application that utilizes Google Calendar API and Gemini AI
for managing calendar events and providing intelligent responses.
"""

import os
import sys
import json
import datetime
from typing import Any
from dotenv import load_dotenv
from google.api_core import exceptions as google_exceptions
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
import google.generativeai as genai
import logging

# .env ファイルから環境変数を読み込む
load_dotenv()


# ロガーの設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 環境変数を取得
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

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

# Google Calendar API クライアントのビルド
try:
    service: Resource = build("calendar", "v3", credentials=CREDENTIALS)
    logger.info("Successfully built the Calendar API client.")
except (ConnectionError, google_exceptions.GoogleAPIError) as e:
    logger.error(f"An error occurred while building the Calendar API client: {e}")
    sys.exit(1)

# 今日の日付を取得
now = datetime.datetime.utcnow()
today = now.date()
logger.debug(f"Today's date: {today}")

# 今週の月曜日の日付を計算
this_week_monday = today - datetime.timedelta(days=today.weekday())
logger.debug(f"This week's Monday: {this_week_monday}")

# 今週の日曜日の日付を計算
this_week_sunday = this_week_monday + datetime.timedelta(days=6)
logger.debug(f"This week's Sunday: {this_week_sunday}")

# 今週の予定を取得
try:
    events_result = (
        service.events()
        .list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=this_week_monday.isoformat() + "T00:00:00Z",
            timeMax=this_week_sunday.isoformat() + "T23:59:59Z",
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])
    logger.info(f"Successfully fetched {len(events)} events from Google Calendar.")
    logger.debug(f"Events: {events}")
except (ConnectionError, google_exceptions.GoogleAPIError) as e:
    logger.error(f"An error occurred while fetching events from Google Calendar: {e}")
    events = []

# 今日の予定をフィルタリング
today_events = []
for event in events:
    start_str = event["start"].get("dateTime", event["start"].get("date"))
    logger.debug(f"Event start time: {start_str}")

    # 日付のみのイベントと終日イベントを考慮
    if "T" in start_str:
        event_date = datetime.datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S%z").date()
    else:
        event_date = datetime.datetime.strptime(start_str, "%Y-%m-%d").date()

    if event_date == today:
        today_events.append(event)
        logger.debug(f"Added event for today: {event}")

# 今日の予定を日本語で整形
if not today_events:
    TODAY_SCHEDULE_TEXT = "今日の予定はありません。"
else:
    TODAY_SCHEDULE_TEXT = "今日の予定は以下の通りです。\n"
    for event in today_events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        summary = event["summary"]

        # 時刻情報を整形
        if "T" in start:
            start_time = datetime.datetime.strptime(
                start, "%Y-%m-%dT%H:%M:%S%z"
            ).strftime("%H:%M")
            EVENT_END_TIME = (
                datetime.datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z").strftime("%H:%M")
                if "T" in end
                else "終日"
            )

            TODAY_SCHEDULE_TEXT += f"- {start_time}から{EVENT_END_TIME}：{summary}\n"
        else:
            TODAY_SCHEDULE_TEXT += f"- 終日：{summary}\n"
    logger.debug(f"Today's schedule text: {TODAY_SCHEDULE_TEXT}")

# Geminiで日本語の文章を生成
model = genai.GenerativeModel("gemini-pro")

PROMPT = f"""
あなたはGoogleカレンダーの情報をわかりやすく伝えるアシスタントAIです。
以下の情報を元に、今日の予定をユーザーに通知してください。
口調は丁寧に、簡潔かつ明瞭に伝えてください。
必ず、以下の「今日の予定」から情報を取り出して文章を作成してください。

今日の予定：
{TODAY_SCHEDULE_TEXT}
"""
try:
    response = model.generate_content(PROMPT)
    logger.info(response.text)
except (ConnectionError, google_exceptions.GoogleAPIError) as e:
    logger.error(f"An error occurred: {e}")
