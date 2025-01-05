"""
Tests for app.py
"""

import sys
import os
from unittest.mock import patch
import pytest
import google.generativeai as genai
from dotenv import load_dotenv
import datetime  # 追加

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# app.py 内で .env を読み込んでいるが、テスト用に再度読み込む
load_dotenv()


# モック用の設定
class MockResponse:
    """Mock response class for testing"""

    def __init__(self, text, prompt_feedback=None, safety_ratings=None):
        self.text = text
        self.prompt_feedback = prompt_feedback
        self.candidates = [self]  # safety_ratingsのために自身をリストに追加
        self.safety_ratings = safety_ratings

    def __iter__(self):
        yield self


@pytest.fixture
def mocked_genai(monkeypatch):
    """
    Fixture for mocking genai functionality
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    monkeypatch.setattr(genai, "configure", lambda **kwargs: None)
    monkeypatch.setattr(
        genai,
        "GenerativeModel",
        lambda model_name: MockGenerativeModel(),
    )

    yield

    # Teardown:
    # 環境変数を元に戻す
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
    else:
        if "GOOGLE_API_KEY" in os.environ:
            del os.environ["GOOGLE_API_KEY"]


class MockGenerativeModel:
    """Mock GenerativeModel class for testing"""

    def generate_content(self, prompt):
        """Generate mock content"""
        if "エラー" in prompt:
            raise ConnectionError("Mocked connection error")
        return MockResponse("Mocked response", prompt_feedback={}, safety_ratings=[])


from app import (
    get_calendar_service,
    fetch_events,
    filter_events,
    format_schedule_text,
    generate_response_text,
    main,
)


def test_get_calendar_service():
    service = get_calendar_service()
    assert service is not None


def test_fetch_events(mocked_genai):
    service = get_calendar_service()
    start_date = datetime.date(2023, 1, 1)
    end_date = datetime.date(2023, 1, 31)
    events = fetch_events(service, start_date, end_date)
    assert isinstance(events, list)


def test_filter_events():
    events = [
        {"start": {"dateTime": "2023-01-01T10:00:00+00:00"}, "summary": "Event 1"},
        {"start": {"dateTime": "2023-01-15T10:00:00+00:00"}, "summary": "Event 2"},
        {"start": {"date": "2023-01-20"}, "summary": "Event 3"},
    ]
    start_date = datetime.date(2023, 1, 1)
    end_date = datetime.date(2023, 1, 31)
    filtered_events = filter_events(events, start_date, end_date)
    assert len(filtered_events) == 3


def test_format_schedule_text():
    filtered_events = [
        {"start": {"dateTime": "2023-01-01T10:00:00+00:00"}, "summary": "Event 1", "end": {"dateTime": "2023-01-01T11:00:00+00:00"}},
        {"start": {"dateTime": "2023-01-15T10:00:00+00:00"}, "summary": "Event 2", "end": {"dateTime": "2023-01-15T11:00:00+00:00"}},
    ]
    period_jp = "今月"
    schedule_text = format_schedule_text(filtered_events, period_jp)
    assert "Event 1" in schedule_text
    assert "Event 2" in schedule_text


def test_generate_response_text(mocked_genai):
    schedule_text = "今月の予定は以下の通りです。\n- 10:00から11:00：Event 1\n"
    period_jp = "今月"
    response_text = generate_response_text(schedule_text, period_jp)
    assert response_text is not None
    assert "Mocked response" in response_text
