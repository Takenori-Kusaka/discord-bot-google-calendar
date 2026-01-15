import pytest
import os
from unittest.mock import patch, MagicMock
from agents.search_agent import SearchAgent


@pytest.fixture
def search_agent():
    # テスト用のダミーAPIキーを設定
    os.environ["GOOGLE_API_KEY"] = "dummy_key"
    os.environ["GOOGLE_SEARCH_ENGINE_ID"] = "dummy_id"
    return SearchAgent()


def test_search_agent_initialization(search_agent):
    assert isinstance(search_agent, SearchAgent)
    assert search_agent.name == "SearchAgent"
    assert len(search_agent.get_functions()) == 3


@pytest.mark.asyncio
@patch("agents.search_agent.build")
async def test_search_agent_google_search(mock_build, search_agent):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.cse().list().execute.return_value = {
        "items": [
            {
                "title": "テスト店舗",
                "link": "http://example.com",
                "snippet": "テスト店舗の説明",
            }
        ]
    }

    response = await search_agent.process("近くのラーメン屋を探して")
    assert isinstance(response, str)
    assert "テスト店舗" in response
    assert "http://example.com" in response


@pytest.mark.asyncio
@patch("agents.search_agent.requests.get")
async def test_search_agent_crawl_webpage(mock_get, search_agent):
    mock_response = MagicMock()
    mock_response.text = """
    <html>
        <head>
            <title>テスト店舗</title>
            <meta name="description" content="テスト店舗の説明">
        </head>
        <body>
            <div class="address">東京都渋谷区</div>
            <div class="hours">10:00-22:00</div>
            <div class="phone">03-1234-5678</div>
        </body>
    </html>
    """
    mock_get.return_value = mock_response

    response = await search_agent.process("テスト店舗の営業時間を教えて")
    assert isinstance(response, str)
    assert "テスト店舗" in response
    assert "10:00-22:00" in response
    assert "東京都渋谷区" in response
    assert "03-1234-5678" in response


@pytest.mark.asyncio
async def test_search_agent_format_results():
    search_data = str(
        {
            "items": [
                {"title": "テスト店舗1", "link": "http://example1.com"},
                {"title": "テスト店舗2", "link": "http://example2.com"},
            ]
        }
    )

    crawl_data = """
    【タイトル】
    テスト店舗1
    
    【住所】
    東京都渋谷区
    
    【営業時間】
    10:00-22:00
    """

    agent = SearchAgent()
    response = agent.format_search_results(search_data, crawl_data)

    assert isinstance(response, str)
    assert "テスト店舗1" in response
    assert "テスト店舗2" in response
    assert "http://example1.com" in response
    assert "http://example2.com" in response
    assert "東京都渋谷区" in response
    assert "10:00-22:00" in response
