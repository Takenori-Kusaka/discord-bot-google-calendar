"""Google Calendar クライアント"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CalendarEvent:
    """カレンダーイベント"""

    def __init__(
        self,
        id: str,
        summary: str,
        start: datetime,
        end: datetime,
        description: str | None = None,
        location: str | None = None,
        all_day: bool = False,
    ):
        self.id = id
        self.summary = summary
        self.start = start
        self.end = end
        self.description = description
        self.location = location
        self.all_day = all_day

    def __repr__(self) -> str:
        return f"CalendarEvent(summary={self.summary!r}, start={self.start})"

    def to_dict(self) -> dict[str, Any]:
        """辞書に変換"""
        return {
            "id": self.id,
            "summary": self.summary,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "description": self.description,
            "location": self.location,
            "all_day": self.all_day,
        }


class GoogleCalendarClient:
    """Google Calendar API クライアント"""

    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

    def __init__(
        self,
        calendar_id: str,
        credentials_path: Path,
        timezone: str = "Asia/Tokyo",
    ):
        """初期化

        Args:
            calendar_id: GoogleカレンダーID
            credentials_path: サービスアカウント認証情報のパス
            timezone: タイムゾーン
        """
        self.calendar_id = calendar_id
        self.timezone = ZoneInfo(timezone)
        self._service = self._build_service(credentials_path)
        logger.info(
            "Google Calendar client initialized",
            calendar_id=calendar_id,
        )

    def _build_service(self, credentials_path: Path):
        """Google Calendar APIサービスを構築"""
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=self.SCOPES,
        )
        return build("calendar", "v3", credentials=credentials)

    async def get_today_events(self) -> list[CalendarEvent]:
        """今日の予定を取得

        Returns:
            list[CalendarEvent]: 今日のイベントリスト
        """
        now = datetime.now(self.timezone)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        return await self._get_events(start_of_day, end_of_day)

    async def get_week_events(self) -> list[CalendarEvent]:
        """今週の予定を取得

        Returns:
            list[CalendarEvent]: 今週のイベントリスト
        """
        now = datetime.now(self.timezone)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week = start_of_day + timedelta(days=7)

        return await self._get_events(start_of_day, end_of_week)

    async def _get_events(
        self,
        time_min: datetime,
        time_max: datetime,
    ) -> list[CalendarEvent]:
        """指定期間のイベントを取得

        Args:
            time_min: 開始日時
            time_max: 終了日時

        Returns:
            list[CalendarEvent]: イベントリスト
        """
        try:
            events_result = (
                self._service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            logger.info(
                "Fetched calendar events",
                count=len(events),
                time_min=time_min.isoformat(),
                time_max=time_max.isoformat(),
            )

            return [self._parse_event(event) for event in events]

        except Exception as e:
            logger.error("Failed to fetch calendar events", error=str(e))
            raise

    def _parse_event(self, event: dict[str, Any]) -> CalendarEvent:
        """APIレスポンスをCalendarEventに変換"""
        start_data = event.get("start", {})
        end_data = event.get("end", {})

        # 終日イベントかどうか
        all_day = "date" in start_data

        if all_day:
            start = datetime.fromisoformat(start_data["date"])
            start = start.replace(tzinfo=self.timezone)
            end = datetime.fromisoformat(end_data["date"])
            end = end.replace(tzinfo=self.timezone)
        else:
            start = datetime.fromisoformat(start_data["dateTime"])
            end = datetime.fromisoformat(end_data["dateTime"])

        return CalendarEvent(
            id=event.get("id", ""),
            summary=event.get("summary", "（タイトルなし）"),
            start=start,
            end=end,
            description=event.get("description"),
            location=event.get("location"),
            all_day=all_day,
        )
