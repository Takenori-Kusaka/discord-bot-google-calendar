import openmeteo_requests
import requests_cache
import retry_requests
import pandas as pd
from datetime import date, timedelta, datetime
import logging
import pytz

# ロガーの設定
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class WeatherClient:
    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude
        self.cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
        self.retry_session = retry_requests.retry(
            self.cache_session, retries=5, backoff_factor=0.2
        )
        self.openmeteo = openmeteo_requests.Client(session=self.retry_session)
        self.weathercode_mapping = {
            0: "晴れ",
            1: "晴れ、曇り",
            2: "晴れ、曇り",
            3: "晴れ、曇り",
            45: "霧",
            48: "霧",
            51: "弱雨",
            53: "並雨",
            55: "並雨",
            56: "みぞれ",
            57: "みぞれ",
            61: "弱雨",
            63: "並雨",
            65: "強雨",
            66: "みぞれ",
            67: "みぞれ",
            71: "弱雪",
            73: "並雪",
            75: "大雪",
            77: "あられ",
            80: "雨",
            81: "雨",
            82: "雨",
            85: "雪",
            86: "雪",
            95: "雷",
            96: "雷、ひょう",
            99: "雷、ひょう",
        }

    def get_weather_data(self, time_range):
        logger.info(
            f"Starting weather data retrieval for {time_range} at lat:{self.latitude}, lon:{self.longitude}"
        )
        try:
            logger.debug("Preparing API parameters")
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "timezone": "Asia/Tokyo",
            }

            if time_range == "today":
                logger.debug("Setting parameters for today's forecast")
                # 日本時間の設定
                jst = pytz.timezone("Asia/Tokyo")
                today_jst = datetime.now(jst).date()

                params.update(
                    {
                        "hourly": [
                            "temperature_2m",
                            "relative_humidity_2m",
                            "precipitation_probability",
                            "weathercode",
                        ],
                        "forecast_days": 1,  # 当日分のデータを取得
                        "past_days": 1,  # 過去1日分のデータを取得
                    }
                )
                logger.debug(f"Using past_days: {params['past_days']}")

            elif time_range == "week":
                logger.debug("Setting parameters for week's forecast")
                params.update(
                    {
                        "daily": [
                            "temperature_2m_max",
                            "temperature_2m_min",
                            "precipitation_sum",
                            "weathercode",
                        ],
                        "forecast_days": 7,
                    }
                )

            logger.info("Making API request")
            responses = self.openmeteo.weather_api(url, params=params)
            # responses[0]を使用してレスポンスを取得
            response = responses[0]
            logger.debug(f"Response type: {type(response)}")

            if time_range == "today":
                logger.debug("Processing hourly data")
                hourly = response.Hourly()
                logger.debug(f"Hourly data type: {type(hourly)}")

                # 変数名とインデックスのマッピング
                variable_indices = {
                    "temperature_2m": 0,
                    "relative_humidity_2m": 1,
                    "precipitation_probability": 2,
                    "weathercode": 3,
                }

                # 時系列データの作成
                hourly_data = {
                    "time": pd.date_range(
                        start=pd.to_datetime(hourly.Time(), unit="s"),
                        end=pd.to_datetime(hourly.TimeEnd(), unit="s"),
                        freq=pd.Timedelta(seconds=hourly.Interval()),
                        inclusive="left",
                    )
                }

                # データの取得
                for variable_name in params["hourly"]:
                    index = variable_indices[variable_name]
                    hourly_data[variable_name] = hourly.Variables(index).ValuesAsNumpy()
                    logger.debug(
                        f"Retrieved data for {variable_name}: {hourly_data[variable_name]}"
                    )

                # DataFrameの作成と日本時間への変換
                df = pd.DataFrame(hourly_data)
                df["time"] = (
                    df["time"].dt.tz_localize("UTC").dt.tz_convert("Asia/Tokyo")
                )

                # 当日の0時から23時までのデータにフィルタリング
                today_start = datetime.now(jst).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                today_end = today_start + timedelta(days=1)
                df = df[(df["time"] >= today_start) & (df["time"] < today_end)]

                # weathercodeを天気情報に変換
                df["weather"] = df["weathercode"].map(self.weathercode_mapping)
                df.drop(columns=["weathercode"], inplace=True)

                logger.debug(f"Created DataFrame with shape: {df.shape}")
                logger.debug(f"Time range: {df['time'].min()} to {df['time'].max()}")

            elif time_range == "week":
                logger.debug("Processing daily data")
                daily = response.Daily()
                logger.debug(f"Daily data type: {type(daily)}")

                # 変数名とインデックスのマッピング
                variable_indices = {
                    "temperature_2m_max": 0,
                    "temperature_2m_min": 1,
                    "precipitation_sum": 2,
                    "weathercode": 3,
                }

                # 日付データの作成
                daily_data = {
                    "time": pd.date_range(
                        start=pd.to_datetime(daily.Time(), unit="s").date(),
                        periods=7,
                        freq="D",
                    )
                }

                # データの取得
                for variable_name in params["daily"]:
                    index = variable_indices[variable_name]
                    daily_data[variable_name] = daily.Variables(index).ValuesAsNumpy()
                    logger.debug(
                        f"Retrieved data for {variable_name}: {daily_data[variable_name]}"
                    )

                # DataFrameの作成
                df = pd.DataFrame(daily_data)

                # weathercodeを天気情報に変換
                df["weather"] = df["weathercode"].map(self.weathercode_mapping)
                df.drop(columns=["weathercode"], inplace=True)

                logger.debug(f"Created DataFrame with shape: {df.shape}")
                logger.debug(f"Date range: {df['time'].min()} to {df['time'].max()}")

            logger.info("Successfully retrieved and processed weather data")
            return df

        except Exception as e:
            logger.error(
                f"Error occurred while retrieving weather data: {str(e)}", exc_info=True
            )
            raise

    def get_weather_markdown(self, time_range):
        if time_range == "month":
            return "月間の天気情報は提供されていません。"
        df = self.get_weather_data(time_range)
        markdown_table = df.to_markdown(index=False)
        return markdown_table
