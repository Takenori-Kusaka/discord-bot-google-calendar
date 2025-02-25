import os
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Optional, Any
import pathlib

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleCalendarAPI:
    """Google Calendar APIのラッパークラス"""
    
    def __init__(self, test_mode: bool = False):
        self.scopes = ['https://www.googleapis.com/auth/calendar']
        self.timezone = ZoneInfo("Asia/Tokyo")
        self.credentials = None
        self.service = None
        self.test_mode = test_mode
        self.initialize_credentials()
        
    def initialize_credentials(self):
        """Google Calendar APIの認証情報を初期化（サービスアカウント）"""
        try:
            # credentials.jsonから認証情報を読み込む
            current_dir = pathlib.Path(__file__).parent.parent
            credentials_path = current_dir / 'credentials.json'
            
            if not credentials_path.exists():
                raise FileNotFoundError(f"Credentials file not found at {credentials_path}")
            
            logger.debug(f"Loading credentials from {credentials_path}")
            self.credentials = service_account.Credentials.from_service_account_file(
                str(credentials_path),
                scopes=self.scopes
            )
            
            # カレンダーサービスの初期化
            self.service = build('calendar', 'v3', credentials=self.credentials)
            logger.info("Google Calendar API service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar API: {e}", exc_info=True)
            if not self.test_mode:
                raise
            logger.warning("Running in test mode - continuing without Google Calendar API")

    def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """カレンダーに新しい予定を作成"""
        try:
            # テストモードの場合はシミュレーション応答を返す
            if self.test_mode or self.service is None:
                logger.info("[TEST MODE] Simulating event creation")
                return {
                    "status": "success",
                    "event": self._simulate_event_creation(event_data),
                    "link": "https://calendar.google.com/calendar/test-event"
                }
            
            # 日時の解析
            start_date = event_data["start"]["date"]
            start_time = event_data["start"]["time"]
            duration_hours = event_data["duration"]["hours"]
            duration_minutes = event_data.get("duration", {}).get("minutes", 0)
            
            # 開始時刻と終了時刻の設定
            start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
            start_dt = start_dt.replace(tzinfo=self.timezone)
            end_dt = start_dt + timedelta(hours=duration_hours, minutes=duration_minutes)
            
            # イベントデータの作成
            event = {
                'summary': event_data.get("summary", "予定"),  # デフォルト値を設定
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': 'Asia/Tokyo',
                },
            }
            
            # オプションフィールドの追加
            if "location" in event_data:
                event['location'] = event_data["location"]
            if "description" in event_data:
                event['description'] = event_data["description"]

            # カレンダーIDの取得
            calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
            
            # イベントの作成
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            logger.info(f"Event '{event['summary']}' created successfully")
            
            return {
                "status": "success",
                "event": self.format_event_for_display(created_event),
                "link": created_event.get('htmlLink')
            }

        except HttpError as error:
            logger.error(f"Google Calendar API error: {error.content}", exc_info=True)
            return {
                "status": "error",
                "message": f"Googleカレンダーのエラー: {str(error)}"
            }
        except Exception as error:
            logger.error(f"Error creating event: {error}", exc_info=True)
            return {
                "status": "error",
                "message": f"予定の作成に失敗しました: {str(error)}"
            }

    def get_events(self, max_results: int = 10) -> Dict[str, Any]:
        """今後の予定を取得"""
        try:
            # テストモードの場合はシミュレーション応答を返す
            if self.test_mode or self.service is None:
                logger.info("[TEST MODE] Simulating event retrieval")
                return {
                    "status": "success",
                    "events": [
                        "テスト予定1\n日時：2025-01-22 10:00〜11:00",
                        "テスト予定2\n日時：2025-01-23 14:00〜15:00"
                    ]
                }
            
            now = datetime.now(self.timezone).isoformat()
            calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
            
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.info(f"Found {len(events)} upcoming events")
            
            formatted_events = [self.format_event_for_display(event) for event in events]
            return {
                "status": "success",
                "events": formatted_events
            }

        except HttpError as error:
            logger.error(f"Google Calendar API error: {error.content}", exc_info=True)
            return {
                "status": "error",
                "message": f"Googleカレンダーのエラー: {str(error)}"
            }
        except Exception as error:
            logger.error(f"Error getting events: {error}", exc_info=True)
            return {
                "status": "error",
                "message": f"予定の取得に失敗しました: {str(error)}"
            }

    def _fix_json_response(self, json_str: str) -> str:
        """ClaudeのJSON応答を修正"""
        # カンマの欠落を修正
        json_str = json_str.replace('"\n    "', '",\n    "')
        json_str = json_str.replace('}\n    "', '},\n    "')
        return json_str

    def _simulate_event_creation(self, event_data: Dict[str, Any]) -> str:
        """テストモード用のイベント作成シミュレーション"""
        start_date = event_data["start"]["date"]
        start_time = event_data["start"]["time"]
        duration_hours = event_data["duration"]["hours"]
        duration_minutes = event_data.get("duration", {}).get("minutes", 0)
        
        start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(hours=duration_hours, minutes=duration_minutes)
        
        event_str = f"{event_data.get('summary', '予定')}\n"
        event_str += f"日時：{start_dt.strftime('%Y-%m-%d %H:%M')}〜{end_dt.strftime('%H:%M')}"
        
        if "location" in event_data:
            event_str += f"\n場所：{event_data['location']}"
        if "description" in event_data:
            event_str += f"\n詳細：{event_data['description']}"
        
        return event_str

    def format_event_for_display(self, event: Dict[str, Any]) -> str:
        """イベントを表示用にフォーマット"""
        try:
            start = event['start'].get('dateTime', event['start'].get('date'))
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            start_dt = start_dt.astimezone(self.timezone)
            
            end = event['end'].get('dateTime', event['end'].get('date'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            end_dt = end_dt.astimezone(self.timezone)
            
            event_str = f"{event.get('summary', '予定')}\n"
            event_str += f"日時：{start_dt.strftime('%Y-%m-%d %H:%M')}〜{end_dt.strftime('%H:%M')}"
            
            if 'location' in event and event['location']:
                event_str += f"\n場所：{event['location']}"
            if 'description' in event and event['description']:
                event_str += f"\n詳細：{event['description']}"
            
            return event_str

        except Exception as error:
            logger.error(f"Error formatting event: {error}", exc_info=True)
            return str(event)  # フォールバック：元のイベントデータを文字列として返す