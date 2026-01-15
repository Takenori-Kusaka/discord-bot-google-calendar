from typing import Dict, Any
import os
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from anthropic import Anthropic
from agents.types import AgentResponse
from agents.google_calendar import GoogleCalendarAPI

# ロガーの設定
logger = logging.getLogger(__name__)


class CalendarAgent:
    """カレンダー操作を担当するエージェント"""

    def __init__(self, test_mode: bool = False):
        self.name = "calendar_agent"
        self.description = "カレンダーの予定管理を担当するエージェント"
        api_key = os.getenv("ANTHROPIC_API_KEY")
        logger.debug(f"Initializing Calendar Agent with API key: {api_key[:6]}...")
        self.client = Anthropic(api_key=api_key)
        self.calendar_api = GoogleCalendarAPI(test_mode=test_mode)
        self.timezone = ZoneInfo("Asia/Tokyo")

        # 現在時刻をシステムプロンプトに含める
        now = datetime.now(self.timezone)
        self.system_prompt = f"""あなたはカレンダー管理の専門家です。
現在時刻は{now.strftime('%Y-%m-%d %H:%M')}です。

ユーザーからの予定に関する要望を理解し、以下のJSON形式で応答してください：
{{
    "summary": "予定のタイトル",
    "start": {{
        "date": "YYYY-MM-DD",      // 現在時刻を基準に適切な日付を設定
        "time": "HH:MM",           // 24時間形式
        "is_tomorrow": true/false  // 「明日」という指定があった場合はtrue
    }},
    "duration": {{
        "hours": 数値,
        "minutes": 数値
    }},
    "location": "場所（指定があれば）",
    "description": "詳細な説明（指定があれば）"
}}

具体例：
{{
    "summary": "プロジェクトミーティング",
    "start": {{
        "date": "2025-01-22",
        "time": "15:00",
        "is_tomorrow": true
    }},
    "duration": {{
        "hours": 1,
        "minutes": 30
    }},
    "location": "会議室A",
    "description": "進捗報告と今後の計画について"
}}

注意事項：
- 必ず有効なJSON形式で応答してください（カンマの位置に注意）
- 日付は必ず"YYYY-MM-DD"形式で指定（例：2025-01-22）
- 時刻は24時間形式で"HH:MM"（例：午後3時は"15:00"）
- 「明日」「来週」などの相対的な日付は現在時刻を基準に計算
- 期間指定がない場合は1時間をデフォルトとする
- 時刻指定がない場合は10:00をデフォルトとする
- 場所やdescriptionは指定がある場合のみ含める
- 現在時刻以降の日時を指定すること

応答は必ずJSON形式のみとし、追加の説明は不要です。
エラーが発生した場合はnullを返してください。
"""
        self.logger = logging.getLogger("Agent.Calendar")
        self.logger.debug(
            "Calendar Agent initialized in %s mode",
            "test" if test_mode else "production",
        )

    async def process(self, input_text: str) -> AgentResponse:
        """エージェントの処理を実行"""
        try:
            # 予定の確認要求の場合
            if "確認" in input_text:
                self.logger.debug("Retrieving calendar events")
                result = self.calendar_api.get_events(max_results=5)
                if result["status"] == "success":
                    events_text = "今後の予定:\n" + "\n\n".join(result["events"])
                    return AgentResponse(agent_name=self.name, response=events_text)
                else:
                    return AgentResponse(
                        agent_name=self.name, response=result["message"]
                    )

            # 予定作成の場合
            self.logger.debug(f"Processing calendar request: {input_text}")
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1024,
                system=self.system_prompt,
                messages=[{"role": "user", "content": input_text}],
            )

            response_text = message.content[0].text if message.content else "null"
            self.logger.debug(f"Claude response: {response_text}")

            try:
                # JSON文字列の修正
                fixed_json = self.calendar_api._fix_json_response(response_text.strip())
                event_data = json.loads(fixed_json)

                if event_data is None:
                    return AgentResponse(
                        agent_name=self.name,
                        response="申し訳ありません。予定の詳細を理解できませんでした。",
                    )

                # Googleカレンダーにイベントを作成
                result = self.calendar_api.create_event(event_data)
                if result["status"] == "success":
                    response = f"""予定を登録しました。

{result["event"]}"""
                    if not self.calendar_api.test_mode and "link" in result:
                        response += f"\n\nカレンダーURL: {result['link']}"
                    return AgentResponse(agent_name=self.name, response=response)
                else:
                    return AgentResponse(
                        agent_name=self.name, response=result["message"]
                    )

            except json.JSONDecodeError as e:
                self.logger.error(
                    f"Failed to parse Claude response as JSON: {e}", exc_info=True
                )
                self.logger.error(f"Raw response: {response_text}")
                return AgentResponse(
                    agent_name=self.name,
                    response="申し訳ありません。予定の解析に失敗しました。もう一度お試しください。",
                )

        except Exception as e:
            self.logger.error(f"Error in calendar agent: {str(e)}", exc_info=True)
            return AgentResponse(
                agent_name=self.name, response=f"エラーが発生しました: {str(e)}"
            )
