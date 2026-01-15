import pytest
import os
from agents.news_agent import NewsAgent


@pytest.fixture
def news_agent():
    # テスト用のダミーAPIキーを設定
    os.environ["PERPLEXITY_API_KEY"] = "dummy_key"
    return NewsAgent()


def test_news_agent_initialization(news_agent):
    assert isinstance(news_agent, NewsAgent)
    assert news_agent.name == "NewsAgent"
    assert len(news_agent.get_functions()) == 2


@pytest.mark.asyncio
async def test_news_agent_process(news_agent):
    response = await news_agent.process("最新のニュースを教えて")
    assert isinstance(response, str)
    assert "ニュース" in response


def test_news_agent_category_detection(news_agent):
    categories = [
        ("経済ニュース", "ビジネス"),
        ("スポーツニュース", "スポーツ"),
        ("科学技術ニュース", "科学技術"),
        ("エンタメニュース", "エンタメ"),
        ("政治ニュース", "政治"),
    ]

    for query, expected_category in categories:
        assert news_agent._determine_category(query) == expected_category


def test_news_agent_query_extraction(news_agent):
    test_cases = [
        ("AIについてのニュース", "AI"),
        ("東京オリンピックについて", "東京オリンピック"),
        ("最新のニュース", ""),  # キーワードなしの場合
    ]

    for query, expected_result in test_cases:
        assert news_agent._extract_query(query) == expected_result
