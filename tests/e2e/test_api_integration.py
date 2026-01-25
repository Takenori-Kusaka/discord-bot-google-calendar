"""E2Eテスト - 実際のAPI呼び出しを含むテスト

これらのテストは実際の外部APIを呼び出すため、以下の条件で実行されます：
- @pytest.mark.e2e マーカーが付与されている
- 環境変数が正しく設定されている
- CIでは --ignore=tests/e2e でスキップされる

費用が発生するAPIテスト（Claude等）は手動実行時のみ有効です。
"""

import os
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo


# E2Eマーカーを定義
pytestmark = pytest.mark.e2e


def skip_if_no_env(var_name: str):
    """環境変数がない場合はスキップ"""
    return pytest.mark.skipif(
        os.environ.get(var_name) is None,
        reason=f"環境変数 {var_name} が設定されていません",
    )


class TestWeatherClientE2E:
    """WeatherClient E2Eテスト（無料API）"""

    @pytest.mark.asyncio
    async def test_get_today_weather_real_api(self):
        """実際のOpenMeteo APIを呼び出す"""
        from src.clients.weather import WeatherClient

        client = WeatherClient(
            latitude=34.7333,  # 木津川市
            longitude=135.8333,
            timezone="Asia/Tokyo",
        )

        weather = await client.get_today_weather()

        # 天気情報が取得できること
        assert weather is not None
        assert weather.weather_description is not None
        assert weather.temperature_max is not None
        assert weather.temperature_min is not None

    @pytest.mark.asyncio
    async def test_get_weather_forecast_real_api(self):
        """週間予報を実際のAPIで取得"""
        from src.clients.weather import WeatherClient

        client = WeatherClient()

        forecasts = await client.get_weather_forecast(days=3)

        assert len(forecasts) == 3
        for forecast in forecasts:
            assert forecast.weather_description is not None


class TestGoogleCalendarClientE2E:
    """GoogleCalendarClient E2Eテスト"""

    @pytest.fixture
    def credentials_path(self):
        """認証情報パス"""
        path = os.environ.get(
            "GOOGLE_CREDENTIALS_PATH", "credentials/calendar-credential.json"
        )
        if not os.path.exists(path):
            pytest.skip(f"認証情報ファイルが存在しません: {path}")
        return path

    @pytest.fixture
    def calendar_id(self):
        """カレンダーID"""
        cal_id = os.environ.get("GOOGLE_CALENDAR_ID")
        if not cal_id:
            pytest.skip("GOOGLE_CALENDAR_ID が設定されていません")
        return cal_id

    @pytest.mark.asyncio
    async def test_get_today_events_real_api(self, credentials_path, calendar_id):
        """実際のGoogle Calendar APIを呼び出す"""
        from src.clients.calendar import GoogleCalendarClient
        from pathlib import Path

        client = GoogleCalendarClient(
            calendar_id=calendar_id,
            credentials_path=Path(credentials_path),
        )

        events = await client.get_today_events()

        # イベントリストが返ること（空でもOK）
        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_get_week_events_real_api(self, credentials_path, calendar_id):
        """今週の予定を実際のAPIで取得"""
        from src.clients.calendar import GoogleCalendarClient
        from pathlib import Path

        client = GoogleCalendarClient(
            calendar_id=calendar_id,
            credentials_path=Path(credentials_path),
        )

        events = await client.get_week_events()

        assert isinstance(events, list)


@skip_if_no_env("ANTHROPIC_API_KEY")
class TestClaudeClientE2E:
    """ClaudeClient E2Eテスト（有料API - 費用発生）"""

    @pytest.fixture
    def api_key(self):
        """APIキー"""
        return os.environ.get("ANTHROPIC_API_KEY")

    @pytest.mark.asyncio
    async def test_generate_butler_message_real_api(self, api_key):
        """実際のClaude APIで執事メッセージを生成"""
        from src.clients.claude import ClaudeClient
        from src.clients.calendar import CalendarEvent

        client = ClaudeClient(api_key=api_key)

        tz = ZoneInfo("Asia/Tokyo")
        events = [
            CalendarEvent(
                id="test-001",
                summary="テスト予定",
                start=datetime(2026, 1, 24, 10, 0, tzinfo=tz),
                end=datetime(2026, 1, 24, 11, 0, tzinfo=tz),
            )
        ]

        message = await client.generate_butler_message(events, butler_name="黒田")

        # 執事口調のメッセージが生成されること
        assert message is not None
        assert len(message) > 0
        # 執事らしい表現が含まれること
        assert any(word in message for word in ["ございます", "旦那様", "黒田"])

    @pytest.mark.asyncio
    async def test_filter_important_events_real_api(self, api_key):
        """実際のClaude APIでイベントフィルタリング"""
        from src.clients.claude import ClaudeClient
        from src.clients.calendar import CalendarEvent

        client = ClaudeClient(api_key=api_key)

        tz = ZoneInfo("Asia/Tokyo")
        events = [
            CalendarEvent(
                id="event-001",
                summary="病院予約",
                start=datetime(2026, 1, 24, 10, 0, tzinfo=tz),
                end=datetime(2026, 1, 24, 11, 0, tzinfo=tz),
                location="木津川市立病院",
            ),
            CalendarEvent(
                id="event-002",
                summary="仕事",
                start=datetime(2026, 1, 24, 9, 0, tzinfo=tz),
                end=datetime(2026, 1, 24, 18, 0, tzinfo=tz),
            ),
        ]

        important = await client.filter_important_events(
            events,
            ignore_patterns=["仕事"],
            notify_patterns=["病院"],
        )

        # フィルタリング結果が返ること
        assert isinstance(important, list)


@skip_if_no_env("GOOGLE_API_KEY")
class TestEventSearchClientE2E:
    """EventSearchClient E2Eテスト"""

    @pytest.mark.asyncio
    async def test_search_events_real_api(self):
        """実際のGoogle Custom Search APIを呼び出す"""
        from src.clients.event_search import EventSearchClient

        api_key = os.environ.get("GOOGLE_API_KEY")
        search_engine_id = os.environ.get("GOOGLE_SEARCH_ENGINE_ID")

        if not search_engine_id:
            pytest.skip("GOOGLE_SEARCH_ENGINE_ID が設定されていません")

        client = EventSearchClient(
            api_key=api_key,
            search_engine_id=search_engine_id,
        )

        results = await client.search_events()

        assert isinstance(results, list)


class TestFullMorningNotificationE2E:
    """朝の通知フルE2Eテスト"""

    @pytest.fixture
    def env_check(self):
        """必要な環境変数のチェック"""
        required = [
            "ANTHROPIC_API_KEY",
            "GOOGLE_CALENDAR_ID",
            "DISCORD_BOT_TOKEN",
        ]
        missing = [var for var in required if not os.environ.get(var)]
        if missing:
            pytest.skip(f"環境変数が不足しています: {missing}")

    @pytest.mark.asyncio
    async def test_morning_notification_dry_run(self, env_check):
        """朝の通知ドライラン（Discord送信はモック）

        このテストは以下を実際に呼び出します：
        - Google Calendar API
        - Claude API
        - OpenMeteo API

        Discord送信のみモックして、メッセージ内容を検証します。
        """
        from unittest.mock import AsyncMock, MagicMock, patch
        from pathlib import Path
        from src.butler import Butler
        from src.clients.calendar import GoogleCalendarClient
        from src.clients.claude import ClaudeClient
        from src.clients.weather import WeatherClient
        from src.config.settings import Settings

        # 設定を読み込み
        settings = MagicMock()
        settings.butler_name = "黒田"
        settings.discord_channel_schedule = "予定"
        settings.timezone = "Asia/Tokyo"
        settings.log_dir = None

        # 実際のクライアントを初期化
        calendar_client = GoogleCalendarClient(
            calendar_id=os.environ["GOOGLE_CALENDAR_ID"],
            credentials_path=Path("credentials/calendar-credential.json"),
        )

        claude_client = ClaudeClient(
            api_key=os.environ["ANTHROPIC_API_KEY"],
        )

        weather_client = WeatherClient()

        # Discordはモック
        mock_discord = AsyncMock()
        mock_discord.send_to_channel = AsyncMock(return_value=True)
        mock_discord.send_error_notification = AsyncMock(return_value=True)
        mock_discord.set_message_handler = MagicMock()

        with patch("src.butler.Path.exists", return_value=False):
            butler = Butler(
                settings=settings,
                calendar_client=calendar_client,
                claude_client=claude_client,
                discord_client=mock_discord,
                weather_client=weather_client,
            )

        # 朝の通知を実行
        await butler.morning_notification()

        # 検証
        mock_discord.send_to_channel.assert_called_once()
        channel_name, message = mock_discord.send_to_channel.call_args[0]

        assert channel_name == "予定"
        assert "黒田" in message
        print(f"\n=== 生成されたメッセージ ===\n{message}\n")
