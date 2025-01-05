"""
Tests for app.py
"""

import os
from unittest.mock import patch
import pytest
import google.generativeai as genai
from dotenv import load_dotenv

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
