import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo
from agents.calendar_agent import CalendarAgent


@pytest.fixture
def calendar_agent():
    return CalendarAgent()


def test_calendar_agent_initialization(calendar_agent):
    assert isinstance(calendar_agent, CalendarAgent)
    assert calendar_agent.name == "CalendarAgent"
    assert len(calendar_agent.get_functions()) == 2  # add_event, parse_datetime


@pytest.mark.asyncio
@patch("anthropic.Client")
@patch("agents.calendar_agent.initialize_calendar_service")
async def test_calendar_agent_add_event(
    mock_initialize, mock_anthropic, calendar_agent
):
    # Anthropic APIのモック設定
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text="""
    {
        "start_time": {
            "year": 2025,
            "month": 1,
            "day": 20,
            "hour": 10,
            "minute": 0
        },
        "end_time": {
            "year": 2025,
            "month": 1,
            "day": 20,
            "hour": 11,
            "minute": 0
        }
    }
    """
        )
    ]
    mock_client.messages.create.return_value = mock_response

    # Googleカレンダーサービスのモック設定
    mock_service = MagicMock()
    mock_initialize.return_value = mock_service
    mock_service.events().insert().execute.return_value = {
        "htmlLink": "http://example.com"
    }

    # テストケース1: 基本的な予定追加
    response = await calendar_agent.process("明日の10時から11時まで会議")
    assert isinstance(response, str)
    assert "予定を追加いたしました" in response
    assert "http://example.com" in response


@pytest.mark.asyncio
@patch("anthropic.Client")
async def test_parse_datetime_variations(mock_anthropic, calendar_agent):
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client

    test_cases = [
        # 基本的な時間指定
        {
            "input": "明日の10時から11時まで",
            "json_response": {
                "start_time": {
                    "year": 2025,
                    "month": 1,
                    "day": 20,
                    "hour": 10,
                    "minute": 0,
                },
                "end_time": {
                    "year": 2025,
                    "month": 1,
                    "day": 20,
                    "hour": 11,
                    "minute": 0,
                },
            },
        },
        # 午前/午後の指定
        {
            "input": "今日の午後3時から5時まで",
            "json_response": {
                "start_time": {
                    "year": 2025,
                    "month": 1,
                    "day": 19,
                    "hour": 15,
                    "minute": 0,
                },
                "end_time": {
                    "year": 2025,
                    "month": 1,
                    "day": 19,
                    "hour": 17,
                    "minute": 0,
                },
            },
        },
        # 分の指定あり
        {
            "input": "明日の10時30分から11時45分まで",
            "json_response": {
                "start_time": {
                    "year": 2025,
                    "month": 1,
                    "day": 20,
                    "hour": 10,
                    "minute": 30,
                },
                "end_time": {
                    "year": 2025,
                    "month": 1,
                    "day": 20,
                    "hour": 11,
                    "minute": 45,
                },
            },
        },
    ]

    for case in test_cases:
        # モックレスポンスの設定
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=str(case["json_response"]))]
        mock_client.messages.create.return_value = mock_response

        # 日時解析のテスト
        start_time, end_time = await calendar_agent.parse_datetime(case["input"])

        # 結果の検証
        assert isinstance(start_time, str)
        assert isinstance(end_time, str)

        # ISO形式の日時文字列をパース
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)

        # タイムゾーンの確認
        assert start_dt.tzinfo == ZoneInfo("Asia/Tokyo")
        assert end_dt.tzinfo == ZoneInfo("Asia/Tokyo")

        # 開始時間と終了時間の順序確認
        assert start_dt < end_dt


@pytest.mark.asyncio
@patch("anthropic.Client")
async def test_parse_datetime_error_handling(mock_anthropic, calendar_agent):
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client

    # APIエラーのシミュレーション
    mock_client.messages.create.side_effect = Exception("API Error")

    # エラー時のデフォルト値の確認
    start_time, end_time = await calendar_agent.parse_datetime("無効な入力")

    # デフォルト値の検証
    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)

    assert start_dt.hour == 10
    assert start_dt.minute == 0
    assert end_dt.hour == 11
    assert end_dt.minute == 0
    assert (end_dt - start_dt).total_seconds() == 3600  # 1時間
    assert start_dt.tzinfo == ZoneInfo("Asia/Tokyo")
