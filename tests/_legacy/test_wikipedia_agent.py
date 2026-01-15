import json
import pytest
from unittest.mock import patch, MagicMock
from agents.wikipedia_agent import WikipediaAgent, DisambiguationError, PageError


@pytest.fixture
def wikipedia_agent():
    return WikipediaAgent()


def test_wikipedia_agent_initialization(wikipedia_agent):
    assert isinstance(wikipedia_agent, WikipediaAgent)
    assert wikipedia_agent.name == "WikipediaAgent"
    assert len(wikipedia_agent.get_functions()) == 3


@pytest.mark.asyncio
@patch("agents.wikipedia_agent.search_wikipedia")
async def test_wikipedia_agent_search(mock_search, wikipedia_agent):
    mock_search.return_value = '["テスト駅", "テスト (プログラミング)", "テスト理論"]'

    # コンテンツのモック
    with patch("agents.wikipedia_agent.get_wikipedia_content") as mock_content:
        mock_content.return_value = json.dumps(
            {
                "summary": "テスト駅に関する要約文です。",
                "url": "https://ja.wikipedia.org/wiki/テスト駅",
            }
        )

        response = await wikipedia_agent.process("テストについて教えて")
        assert isinstance(response, str)
        assert "テスト駅" in response
        assert "テスト (プログラミング)" in response
        assert "テスト理論" in response


@pytest.mark.asyncio
@patch("agents.wikipedia_agent.get_wikipedia_content")
async def test_wikipedia_agent_get_content(mock_get_content, wikipedia_agent):
    mock_get_content.return_value = json.dumps(
        {
            "summary": "テストに関する要約文です。",
            "url": "https://ja.wikipedia.org/wiki/テスト",
        }
    )

    response = await wikipedia_agent.process("テストの詳細を教えて")
    assert isinstance(response, str)
    assert "テストに関する要約文です" in response
    assert "https://ja.wikipedia.org/wiki/テスト" in response


@pytest.mark.asyncio
@patch("agents.wikipedia_agent.get_wikipedia_content")
async def test_wikipedia_agent_disambiguation(mock_get_content, wikipedia_agent):
    mock_get_content.return_value = json.dumps(
        {
            "error": True,
            "message": "'テスト' は曖昧さ回避ページです。",
            "options": ["テスト (評価)", "テスト (工学)", "テスト (心理学)"],
        }
    )

    response = await wikipedia_agent.process("テストについて教えて")
    assert isinstance(response, str)
    assert "複数の意味" in response
    assert "テスト (評価)" in response
    assert "テスト (工学)" in response
    assert "テスト (心理学)" in response


@pytest.mark.asyncio
@patch("agents.wikipedia_agent.get_wikipedia_content")
async def test_wikipedia_agent_page_not_found(mock_get_content, wikipedia_agent):
    mock_get_content.return_value = json.dumps(
        {"error": True, "message": "ページ '存在しないページ' は存在しません。"}
    )

    response = await wikipedia_agent.process("存在しないページについて教えて")
    assert isinstance(response, str)
    assert "存在しません" in response


def test_wikipedia_agent_format_info():
    agent = WikipediaAgent()

    # 検索結果のみの場合
    search_data = '["テスト1", "テスト2", "テスト3"]'
    formatted = agent.format_wikipedia_info(search_data)
    assert isinstance(formatted, str)
    assert "テスト1" in formatted
    assert "テスト2" in formatted
    assert "テスト3" in formatted

    # 検索結果とページ内容がある場合
    content_data = json.dumps(
        {
            "summary": "テストの要約文です。",
            "url": "https://ja.wikipedia.org/wiki/テスト",
        }
    )
    formatted = agent.format_wikipedia_info(search_data, content_data)
    assert isinstance(formatted, str)
    assert "テストの要約文です" in formatted
    assert "https://ja.wikipedia.org/wiki/テスト" in formatted

    # 曖昧さ回避の場合
    disambiguation_data = json.dumps(
        {
            "error": True,
            "message": "'テスト' は曖昧さ回避ページです。",
            "options": ["テスト (評価)", "テスト (工学)", "テスト (心理学)"],
        }
    )
    formatted = agent.format_wikipedia_info(search_data, disambiguation_data)
    assert isinstance(formatted, str)
    assert "複数の意味" in formatted
    assert "テスト (評価)" in formatted
    assert "テスト (工学)" in formatted
    assert "テスト (心理学)" in formatted
