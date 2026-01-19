"""天気予報クライアント（OpenMeteo API）"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import aiohttp

from ..utils.logger import get_logger

logger = get_logger(__name__)

# 木津川市の座標
KIZUGAWA_LATITUDE = 34.7333
KIZUGAWA_LONGITUDE = 135.8333

# 天気コードの日本語マッピング
WEATHER_CODES = {
    0: "快晴",
    1: "晴れ",
    2: "一部曇り",
    3: "曇り",
    45: "霧",
    48: "霧氷",
    51: "弱い霧雨",
    53: "霧雨",
    55: "強い霧雨",
    56: "弱い凍結霧雨",
    57: "強い凍結霧雨",
    61: "弱い雨",
    63: "雨",
    65: "強い雨",
    66: "弱い凍結雨",
    67: "強い凍結雨",
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
    96: "雷雨（弱い雹）",
    99: "雷雨（強い雹）",
}


@dataclass
class WeatherInfo:
    """天気情報"""

    date: datetime
    weather_code: int
    weather_description: str
    temperature_max: float
    temperature_min: float
    precipitation_probability: int
    precipitation_sum: float
    sunrise: Optional[str] = None
    sunset: Optional[str] = None

    def format_for_notification(self) -> str:
        """通知用にフォーマット"""
        lines = [
            f"天気: {self.weather_description}",
            f"気温: {self.temperature_min:.0f}°C 〜 {self.temperature_max:.0f}°C",
        ]

        if self.precipitation_probability > 0:
            lines.append(f"降水確率: {self.precipitation_probability}%")

        return " / ".join(lines)


class WeatherClient:
    """天気予報クライアント（OpenMeteo API）"""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(
        self,
        latitude: float = KIZUGAWA_LATITUDE,
        longitude: float = KIZUGAWA_LONGITUDE,
        timezone: str = "Asia/Tokyo",
    ):
        """初期化

        Args:
            latitude: 緯度
            longitude: 経度
            timezone: タイムゾーン
        """
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        logger.info(
            "Weather client initialized",
            latitude=latitude,
            longitude=longitude,
        )

    async def get_today_weather(self) -> Optional[WeatherInfo]:
        """今日の天気を取得

        Returns:
            WeatherInfo: 今日の天気情報
        """
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "precipitation_sum",
                "sunrise",
                "sunset",
            ],
            "timezone": self.timezone,
            "forecast_days": 1,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params) as response:
                    if response.status != 200:
                        logger.warning(f"Weather API error: {response.status}")
                        return None

                    data = await response.json()
                    daily = data.get("daily", {})

                    if not daily.get("time"):
                        logger.warning("No weather data available")
                        return None

                    weather_code = daily["weather_code"][0]
                    weather_description = WEATHER_CODES.get(weather_code, "不明")

                    weather = WeatherInfo(
                        date=datetime.now(ZoneInfo(self.timezone)),
                        weather_code=weather_code,
                        weather_description=weather_description,
                        temperature_max=daily["temperature_2m_max"][0],
                        temperature_min=daily["temperature_2m_min"][0],
                        precipitation_probability=daily[
                            "precipitation_probability_max"
                        ][0]
                        or 0,
                        precipitation_sum=daily["precipitation_sum"][0] or 0,
                        sunrise=daily.get("sunrise", [None])[0],
                        sunset=daily.get("sunset", [None])[0],
                    )

                    logger.info(
                        "Weather fetched",
                        weather=weather_description,
                        temp_max=weather.temperature_max,
                        temp_min=weather.temperature_min,
                    )

                    return weather

        except Exception as e:
            logger.error(f"Failed to fetch weather: {e}")
            return None

    async def get_weather_forecast(self, days: int = 7) -> list[WeatherInfo]:
        """複数日の天気予報を取得

        Args:
            days: 取得する日数（最大16日）

        Returns:
            list[WeatherInfo]: 天気予報リスト
        """
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "precipitation_sum",
            ],
            "timezone": self.timezone,
            "forecast_days": min(days, 16),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params) as response:
                    if response.status != 200:
                        logger.warning(f"Weather API error: {response.status}")
                        return []

                    data = await response.json()
                    daily = data.get("daily", {})

                    if not daily.get("time"):
                        return []

                    forecasts = []
                    for i, date_str in enumerate(daily["time"]):
                        weather_code = daily["weather_code"][i]
                        forecasts.append(
                            WeatherInfo(
                                date=datetime.fromisoformat(date_str).replace(
                                    tzinfo=ZoneInfo(self.timezone)
                                ),
                                weather_code=weather_code,
                                weather_description=WEATHER_CODES.get(
                                    weather_code, "不明"
                                ),
                                temperature_max=daily["temperature_2m_max"][i],
                                temperature_min=daily["temperature_2m_min"][i],
                                precipitation_probability=daily[
                                    "precipitation_probability_max"
                                ][i]
                                or 0,
                                precipitation_sum=daily["precipitation_sum"][i] or 0,
                            )
                        )

                    logger.info(f"Fetched {len(forecasts)} days forecast")
                    return forecasts

        except Exception as e:
            logger.error(f"Failed to fetch forecast: {e}")
            return []
