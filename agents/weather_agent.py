from typing import Dict, Any, Optional
import os
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from anthropic import Anthropic
from agents.types import AgentResponse
from agents.google_places import GooglePlacesClient
from agents.openmeteo_client import OpenMeteoClient

logger = logging.getLogger(__name__)

class WeatherAgent:
    """天気情報を提供するエージェント"""
    
    def __init__(self):
        self.name = "weather_agent"
        self.description = "天気情報の取得と提供を担当するエージェント"
        api_key = os.getenv("ANTHROPIC_API_KEY")
        logger.debug(f"Initializing Weather Agent with API key: {api_key[:6]}...")
        
        self.client = Anthropic(api_key=api_key)
        self.places_client = GooglePlacesClient()
        self.weather_client = OpenMeteoClient()
        self.timezone = ZoneInfo("Asia/Tokyo")
        
        # 現在時刻をシステムプロンプトに含める
        now = datetime.now(self.timezone)
        self.system_prompt = f"""あなたは天気予報の専門家です。
現在時刻は{now.strftime('%Y-%m-%d %H:%M')}です。

ユーザーからの天気に関する要望を理解し、以下のJSON形式で応答してください：

{{
    "location": "場所の名前",
    "period": {{
        "start_date": "YYYY-MM-DD",  // 現在時刻を基準に適切な日付を設定
        "end_date": "YYYY-MM-DD",    // 期間指定がある場合のみ
        "time": "HH:MM",             // 時刻指定がある場合のみ（24時間形式）
        "is_range": true/false       // 期間指定があるかどうか
    }}
}}

例1（特定の日時）：
入力: 「明日の15時の東京の天気」
{{
    "location": "東京",
    "period": {{
        "start_date": "2025-01-22",
        "time": "15:00",
        "is_range": false
    }}
}}

例2（期間指定）：
入力: 「今週末の大阪の天気」
{{
    "location": "大阪",
    "period": {{
        "start_date": "2025-01-25",
        "end_date": "2025-01-26",
        "is_range": true
    }}
}}

注意事項：
- 場所が指定されていない場合は木津川市を使用
- 日付は必ず"YYYY-MM-DD"形式で指定
- 時刻は24時間形式で"HH:MM"
- 「明日」「来週」などの相対的な日付は現在時刻を基準に計算
- 期間指定がない場合は当日のみ
- 時刻指定がない場合は終日の予報を提供

応答は必ずJSON形式のみとし、追加の説明は不要です。
エラーが発生した場合はnullを返してください。
"""
        self.logger = logging.getLogger("Agent.Weather")
        self.logger.debug("Weather Agent initialized")

    def _parse_date(self, date_str: str) -> datetime:
        """日付文字列をdatetimeオブジェクトに変換"""
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=self.timezone)

    async def process(self, input_text: str) -> AgentResponse:
        """エージェントの処理を実行"""
        try:
            # Claudeで入力を解析
            self.logger.debug(f"Processing weather request: {input_text}")
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1024,
                system=self.system_prompt,
                messages=[{"role": "user", "content": input_text}]
            )
            
            response_text = message.content[0].text if message.content else "null"
            self.logger.debug(f"Claude response: {response_text}")
            
            try:
                query_data = json.loads(response_text.strip())
                if query_data is None:
                    return AgentResponse(
                        agent_name=self.name,
                        response="申し訳ありません。ご要望を理解できませんでした。"
                    )
                
                # 場所の緯度経度を取得
                location = self.places_client.search_location(query_data["location"])
                self.logger.debug(f"Location data: {location}")
                
                # 日時の処理
                period = query_data["period"]
                start_date = self._parse_date(period["start_date"])
                end_date = (
                    self._parse_date(period["end_date"])
                    if "end_date" in period and period["is_range"]
                    else start_date
                )
                
                if "time" in period:
                    hour, minute = map(int, period["time"].split(":"))
                    start_date = start_date.replace(hour=hour, minute=minute)
                    end_date = end_date.replace(hour=hour, minute=minute)
                
                # 天気情報を取得
                weather_data = self.weather_client.get_weather(
                    latitude=location["latitude"],
                    longitude=location["longitude"],
                    start_date=start_date,
                    end_date=end_date
                )
                
                # レスポンスの作成
                weather_text = self.weather_client.format_weather_text(weather_data)
                response = f"""{location['name']}の天気予報です。

{weather_text}"""
                
                return AgentResponse(agent_name=self.name, response=response)
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse Claude response as JSON: {e}", exc_info=True)
                return AgentResponse(
                    agent_name=self.name,
                    response="申し訳ありません。天気予報の解析に失敗しました。もう一度お試しください。"
                )
            
        except Exception as e:
            self.logger.error(f"Error in weather agent: {str(e)}", exc_info=True)
            return AgentResponse(
                agent_name=self.name,
                response=f"エラーが発生しました: {str(e)}"
            )
