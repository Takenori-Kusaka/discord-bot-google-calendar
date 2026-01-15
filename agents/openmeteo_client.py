import openmeteo_requests
import requests_cache
import retry_requests
import pandas as pd
from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OpenMeteoClient:
    """OpenMeteo APIを使用して天気情報を取得するクライアント"""

    def __init__(self):
        # キャッシュの設定
        self.cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
        self.retry_session = retry_requests.retry(
            self.cache_session, retries=5, backoff_factor=0.2
        )
        self.openmeteo = openmeteo_requests.Client(session=self.retry_session)
        self.timezone = ZoneInfo("Asia/Tokyo")

        # 天気コードのマッピング
        self.weathercode_mapping = {
            0: "晴れ",
            1: "晴れ、薄い雲",
            2: "晴れ、雲あり",
            3: "曇り",
            45: "霧",
            48: "霧氷",
            51: "弱い霧雨",
            53: "霧雨",
            55: "強い霧雨",
            56: "凍る霧雨",
            57: "強い凍る霧雨",
            61: "弱い雨",
            63: "雨",
            65: "強い雨",
            66: "凍る雨",
            67: "強い凍る雨",
            71: "弱い雪",
            73: "雪",
            75: "強い雪",
            77: "霧雪",
            80: "弱いにわか雨",
            81: "にわか雨",
            82: "強いにわか雨",
            85: "弱いにわか雪",
            86: "強いにわか雪",
            95: "雷雨",
            96: "雷雨とあられ",
            99: "強い雷雨とあられ",
        }

    def get_weather(
        self,
        latitude: float,
        longitude: float,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """天気情報を取得"""
        try:
            now = datetime.now(self.timezone)
            if not start_date:
                start_date = now
            if not end_date:
                end_date = start_date + timedelta(days=1)

            # 日数を計算
            days_diff = (end_date.date() - start_date.date()).days + 1
            logger.debug(f"Fetching weather for {days_diff} days")

            # APIパラメータの設定
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": "Asia/Tokyo",
            }

            if days_diff <= 1:
                # 1日以内の場合は1時間ごとのデータ
                params.update(
                    {
                        "hourly": [
                            "temperature_2m",
                            "relative_humidity_2m",
                            "precipitation_probability",
                            "weathercode",
                            "apparent_temperature",
                        ],
                        "daily": [
                            "temperature_2m_max",
                            "temperature_2m_min",
                            "precipitation_sum",
                            "weathercode",
                        ],
                        "forecast_days": 1,
                    }
                )
            else:
                # 複数日の場合は日ごとのデータ
                params.update(
                    {
                        "daily": [
                            "temperature_2m_max",
                            "temperature_2m_min",
                            "precipitation_sum",
                            "weathercode",
                            "precipitation_probability_max",
                        ],
                        "forecast_days": min(days_diff, 7),  # 最大7日
                    }
                )

            # APIリクエスト
            response = self.openmeteo.weather_api(url, params=params)[0]

            result = {
                "location": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
            }

            if days_diff <= 1:
                # 1日の詳細データを処理
                hourly = response.Hourly()
                hourly_data = []

                for i in range(len(hourly.Variables(0).ValuesAsNumpy())):
                    hour_data = {
                        "time": datetime.fromtimestamp(
                            hourly.Time()[i], self.timezone
                        ).strftime("%H:%M"),
                        "temperature": round(hourly.Variables(0).ValuesAsNumpy()[i], 1),
                        "humidity": round(hourly.Variables(1).ValuesAsNumpy()[i]),
                        "precipitation_prob": round(
                            hourly.Variables(2).ValuesAsNumpy()[i]
                        ),
                        "weather": self.weathercode_mapping.get(
                            int(hourly.Variables(3).ValuesAsNumpy()[i]), "不明"
                        ),
                        "apparent_temp": round(
                            hourly.Variables(4).ValuesAsNumpy()[i], 1
                        ),
                    }
                    hourly_data.append(hour_data)

                # 日ごとの概要も追加
                daily = response.Daily()
                result.update(
                    {
                        "today": {
                            "max_temp": round(daily.Variables(0).ValuesAsNumpy()[0], 1),
                            "min_temp": round(daily.Variables(1).ValuesAsNumpy()[0], 1),
                            "precipitation_sum": round(
                                daily.Variables(2).ValuesAsNumpy()[0], 1
                            ),
                            "weather": self.weathercode_mapping.get(
                                int(daily.Variables(3).ValuesAsNumpy()[0]), "不明"
                            ),
                        },
                        "hourly": hourly_data,
                    }
                )

            else:
                # 複数日のデータを処理
                daily = response.Daily()
                daily_data = []

                for i in range(len(daily.Variables(0).ValuesAsNumpy())):
                    day_data = {
                        "date": datetime.fromtimestamp(
                            daily.Time()[i], self.timezone
                        ).strftime("%Y-%m-%d"),
                        "max_temp": round(daily.Variables(0).ValuesAsNumpy()[i], 1),
                        "min_temp": round(daily.Variables(1).ValuesAsNumpy()[i], 1),
                        "precipitation_sum": round(
                            daily.Variables(2).ValuesAsNumpy()[i], 1
                        ),
                        "weather": self.weathercode_mapping.get(
                            int(daily.Variables(3).ValuesAsNumpy()[i]), "不明"
                        ),
                        "precipitation_prob": round(
                            daily.Variables(4).ValuesAsNumpy()[i]
                        ),
                    }
                    daily_data.append(day_data)

                result["daily"] = daily_data

            return result

        except Exception as e:
            logger.error(f"Error getting weather data: {str(e)}", exc_info=True)
            raise

    def format_weather_text(self, weather_data: Dict[str, Any]) -> str:
        """天気情報を読みやすいテキストに整形"""
        try:
            text = []

            if "today" in weather_data:
                # 1日の天気
                today = weather_data["today"]
                text.append(f"本日の天気: {today['weather']}")
                text.append(f"気温: {today['min_temp']}°C 〜 {today['max_temp']}°C")
                if today["precipitation_sum"] > 0:
                    text.append(f"降水量: {today['precipitation_sum']}mm")

                # 3時間ごとの主要な情報
                hourly = weather_data["hourly"]
                important_hours = [6, 9, 12, 15, 18, 21]  # 主要な時間帯

                text.append("\n時間ごとの天気:")
                for hour in hourly:
                    hour_num = int(hour["time"].split(":")[0])
                    if hour_num in important_hours:
                        text.append(
                            f"{hour['time']}: {hour['weather']} "
                            f"{hour['temperature']}°C（体感温度: {hour['apparent_temp']}°C）"
                            f" 降水確率: {hour['precipitation_prob']}%"
                        )

            else:
                # 複数日の天気
                text.append("天気予報:")
                for day in weather_data["daily"]:
                    text.append(
                        f"\n{day['date']}: {day['weather']}\n"
                        f"気温: {day['min_temp']}°C 〜 {day['max_temp']}°C\n"
                        f"降水確率: {day['precipitation_prob']}%"
                    )
                    if day["precipitation_sum"] > 0:
                        text.append(f"降水量: {day['precipitation_sum']}mm")

            return "\n".join(text)

        except Exception as e:
            logger.error(f"Error formatting weather text: {str(e)}", exc_info=True)
            return "天気情報の形式化に失敗しました。"
