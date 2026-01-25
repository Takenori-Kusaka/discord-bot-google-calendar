"""Weather クライアントの単体テスト"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from zoneinfo import ZoneInfo
import aiohttp

from src.clients.weather import WeatherClient, WeatherInfo, WEATHER_CODES


class TestWeatherInfo:
    """WeatherInfoクラスのテスト"""

    def test_weather_info_creation(self):
        """WeatherInfoの作成"""
        tz = ZoneInfo("Asia/Tokyo")
        weather = WeatherInfo(
            date=datetime(2026, 1, 24, tzinfo=tz),
            weather_code=1,
            weather_description="晴れ",
            temperature_max=12.0,
            temperature_min=3.0,
            precipitation_probability=10,
            precipitation_sum=0.0,
            sunrise="06:58",
            sunset="17:12",
        )

        assert weather.weather_description == "晴れ"
        assert weather.temperature_max == 12.0
        assert weather.temperature_min == 3.0
        assert weather.precipitation_probability == 10

    def test_format_for_notification_sunny(self):
        """晴れの日の通知フォーマット"""
        tz = ZoneInfo("Asia/Tokyo")
        weather = WeatherInfo(
            date=datetime(2026, 1, 24, tzinfo=tz),
            weather_code=1,
            weather_description="晴れ",
            temperature_max=12.0,
            temperature_min=3.0,
            precipitation_probability=0,
            precipitation_sum=0.0,
        )

        result = weather.format_for_notification()

        assert "晴れ" in result
        assert "12°C" in result
        assert "3°C" in result
        # 降水確率0%の場合は表示されない
        assert "降水確率" not in result

    def test_format_for_notification_rainy(self):
        """雨の日の通知フォーマット"""
        tz = ZoneInfo("Asia/Tokyo")
        weather = WeatherInfo(
            date=datetime(2026, 1, 24, tzinfo=tz),
            weather_code=63,
            weather_description="雨",
            temperature_max=10.0,
            temperature_min=5.0,
            precipitation_probability=80,
            precipitation_sum=15.0,
        )

        result = weather.format_for_notification()

        assert "雨" in result
        assert "降水確率: 80%" in result


class TestWeatherCodes:
    """天気コードマッピングのテスト"""

    def test_weather_code_clear(self):
        """快晴コード"""
        assert WEATHER_CODES[0] == "快晴"

    def test_weather_code_cloudy(self):
        """曇りコード"""
        assert WEATHER_CODES[3] == "曇り"

    def test_weather_code_rain(self):
        """雨コード"""
        assert WEATHER_CODES[63] == "雨"

    def test_weather_code_snow(self):
        """雪コード"""
        assert WEATHER_CODES[73] == "雪"

    def test_weather_code_thunderstorm(self):
        """雷雨コード"""
        assert WEATHER_CODES[95] == "雷雨"


class TestWeatherClient:
    """WeatherClientクラスのテスト"""

    @pytest.fixture
    def weather_client(self):
        """WeatherClientのインスタンス"""
        return WeatherClient(
            latitude=34.7333,
            longitude=135.8333,
            timezone="Asia/Tokyo",
        )

    @pytest.fixture
    def mock_weather_response(self):
        """天気APIレスポンスのモック"""
        return {
            "daily": {
                "time": ["2026-01-24"],
                "weather_code": [1],
                "temperature_2m_max": [12.0],
                "temperature_2m_min": [3.0],
                "precipitation_probability_max": [10],
                "precipitation_sum": [0.0],
                "sunrise": ["2026-01-24T06:58"],
                "sunset": ["2026-01-24T17:12"],
            }
        }

    @pytest.mark.asyncio
    async def test_get_today_weather_success(
        self, weather_client, mock_weather_response
    ):
        """今日の天気を正常に取得"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_weather_response)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("src.clients.weather.aiohttp.ClientSession", return_value=mock_session_cm):
            weather = await weather_client.get_today_weather()

            assert weather is not None
            assert weather.weather_description == "晴れ"
            assert weather.temperature_max == 12.0
            assert weather.temperature_min == 3.0

    @pytest.mark.asyncio
    async def test_get_today_weather_api_error(self, weather_client):
        """API エラー時はNoneを返す"""
        mock_response = AsyncMock()
        mock_response.status = 500

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_context

        mock_session_context = AsyncMock()
        mock_session_context.__aenter__.return_value = mock_session
        mock_session_context.__aexit__.return_value = None

        with patch("src.clients.weather.aiohttp.ClientSession", return_value=mock_session_context):
            weather = await weather_client.get_today_weather()

            assert weather is None

    @pytest.mark.asyncio
    async def test_get_today_weather_no_data(self, weather_client):
        """データなしの場合はNoneを返す"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"daily": {"time": []}})

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_context

        mock_session_context = AsyncMock()
        mock_session_context.__aenter__.return_value = mock_session
        mock_session_context.__aexit__.return_value = None

        with patch("src.clients.weather.aiohttp.ClientSession", return_value=mock_session_context):
            weather = await weather_client.get_today_weather()

            assert weather is None

    @pytest.mark.asyncio
    async def test_get_today_weather_network_error(self, weather_client):
        """ネットワークエラー時はNoneを返す"""
        mock_context = AsyncMock()
        mock_context.__aenter__.side_effect = Exception("Network Error")

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_context

        mock_session_context = AsyncMock()
        mock_session_context.__aenter__.return_value = mock_session
        mock_session_context.__aexit__.return_value = None

        with patch("src.clients.weather.aiohttp.ClientSession", return_value=mock_session_context):
            weather = await weather_client.get_today_weather()

            assert weather is None

    @pytest.mark.asyncio
    async def test_get_weather_forecast_success(self, weather_client):
        """週間予報を正常に取得"""
        forecast_response = {
            "daily": {
                "time": ["2026-01-24", "2026-01-25", "2026-01-26"],
                "weather_code": [1, 3, 63],
                "temperature_2m_max": [12.0, 10.0, 8.0],
                "temperature_2m_min": [3.0, 2.0, 4.0],
                "precipitation_probability_max": [10, 30, 80],
                "precipitation_sum": [0.0, 0.0, 15.0],
            }
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=forecast_response)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("src.clients.weather.aiohttp.ClientSession", return_value=mock_session_cm):
            forecasts = await weather_client.get_weather_forecast(days=3)

            assert len(forecasts) == 3
            assert forecasts[0].weather_description == "晴れ"
            assert forecasts[1].weather_description == "曇り"
            assert forecasts[2].weather_description == "雨"

    @pytest.mark.asyncio
    async def test_get_weather_forecast_api_error(self, weather_client):
        """予報取得時のAPIエラー"""
        mock_response = AsyncMock()
        mock_response.status = 500

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_context

        mock_session_context = AsyncMock()
        mock_session_context.__aenter__.return_value = mock_session
        mock_session_context.__aexit__.return_value = None

        with patch("src.clients.weather.aiohttp.ClientSession", return_value=mock_session_context):
            forecasts = await weather_client.get_weather_forecast(days=7)

            assert forecasts == []

    def test_unknown_weather_code(self, weather_client):
        """未知の天気コードは「不明」として処理"""
        # WEATHER_CODESに存在しないコードをテスト
        unknown_code = 999
        description = WEATHER_CODES.get(unknown_code, "不明")
        assert description == "不明"

    @pytest.mark.asyncio
    async def test_get_weather_with_null_precipitation(self, weather_client):
        """降水確率がNullの場合の処理"""
        response_with_null = {
            "daily": {
                "time": ["2026-01-24"],
                "weather_code": [1],
                "temperature_2m_max": [12.0],
                "temperature_2m_min": [3.0],
                "precipitation_probability_max": [None],
                "precipitation_sum": [None],
                "sunrise": ["2026-01-24T06:58"],
                "sunset": ["2026-01-24T17:12"],
            }
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=response_with_null)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("src.clients.weather.aiohttp.ClientSession", return_value=mock_session_cm):
            weather = await weather_client.get_today_weather()

            assert weather is not None
            assert weather.precipitation_probability == 0
            assert weather.precipitation_sum == 0
