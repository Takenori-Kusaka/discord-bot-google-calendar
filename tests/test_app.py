"""
Tests for app.py
"""

import os
import pytest
from unittest.mock import patch
import google.generativeai as genai
from dotenv import load_dotenv

# app.py 内で .env を読み込んでいるが、テスト用に再度読み込む
load_dotenv()


# モック用の設定
class MockResponse:
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
    Configures genai and model for tests, and cleanup afterwards.
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
    """
    Mocks the GenerativeModel class for testing.
    """

    def generate_content(self, prompt):
        """
        Mocks the generate_content method for testing.
        """
        if "エラー" in prompt:
            raise ConnectionError("Mocked connection error")
        return MockResponse("Mocked response", prompt_feedback={}, safety_ratings=[])


def test_generate_content_success(mocked_genai):
    """
    Tests successful content generation.
    """
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content("日本の首都はどこですか？")
    assert response.text == "Mocked response"
    assert response.prompt_feedback == {}


def test_generate_content_connection_error(mocked_genai):
    """
    Tests content generation with a connection error.
    """
    model = genai.GenerativeModel("gemini-pro")
    with pytest.raises(ConnectionError) as e:
        model.generate_content("エラー")
    assert str(e.value) == "Mocked connection error"
