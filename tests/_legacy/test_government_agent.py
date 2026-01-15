import pytest
from unittest.mock import patch, MagicMock
from agents.government_agent import GovernmentAgent


@pytest.fixture
def government_agent():
    return GovernmentAgent()


def test_government_agent_initialization(government_agent):
    assert isinstance(government_agent, GovernmentAgent)
    assert government_agent.name == "GovernmentAgent"
    assert len(government_agent.get_functions()) == 2
    assert len(government_agent.sources) == 10  # 10の政府・自治体機関


@pytest.mark.asyncio
@patch("agents.government_agent.requests.get")
async def test_government_agent_process_general(mock_get, government_agent):
    mock_response = MagicMock()
    mock_response.text = """
    <html>
        <body>
            <h2 class="title">テスト政策について</h2>
            <a href="/policy/detail.html">詳細はこちら</a>
            <h2 class="title">関連情報</h2>
            <a href="/info/related.html">参考リンク</a>
        </body>
    </html>
    """
    mock_get.return_value = mock_response

    response = await government_agent.process("文部科学省の最新情報を教えて")
    assert isinstance(response, str)
    assert "文部科学省" in response
    assert "テスト政策について" in response


@pytest.mark.asyncio
@patch("agents.government_agent.requests.get")
async def test_government_agent_process_with_query(mock_get, government_agent):
    mock_response = MagicMock()
    mock_response.text = """
    <html>
        <body>
            <h2 class="title">教育政策の最新動向</h2>
            <a href="/education/policy.html">詳細はこちら</a>
            <h2 class="title">教育関連情報</h2>
            <a href="/education/info.html">参考リンク</a>
        </body>
    </html>
    """
    mock_get.return_value = mock_response

    response = await government_agent.process("文部科学省の教育政策について教えて")
    assert isinstance(response, str)
    assert "文部科学省" in response
    assert "教育政策" in response


@pytest.mark.asyncio
async def test_government_agent_multiple_sources():
    agent = GovernmentAgent()

    # 各情報源のURLが正しく設定されているか確認
    assert agent.sources["総務省"] == "https://www.soumu.go.jp"
    assert agent.sources["文部科学省"] == "https://www.mext.go.jp"
    assert agent.sources["農林水産省"] == "https://www.maff.go.jp"
    assert agent.sources["デジタル庁"] == "https://www.digital.go.jp"
    assert agent.sources["子ども家庭庁"] == "https://www.cfa.go.jp"
    assert agent.sources["内閣府"] == "https://www.cao.go.jp"
    assert agent.sources["国土交通省"] == "https://www.mlit.go.jp"
    assert agent.sources["財務省"] == "https://www.mof.go.jp"
    assert agent.sources["京都府"] == "https://www.pref.kyoto.jp"
    assert agent.sources["木津川市"] == "https://www.city.kizugawa.lg.jp"


def test_government_agent_format_info():
    agent = GovernmentAgent()

    # 情報の整形をテスト
    source = "文部科学省"
    info = "教育政策の最新情報\n詳細はこちら: https://example.com"

    formatted = agent.format_government_info(source, info)
    assert isinstance(formatted, str)
    assert "【文部科学省】" in formatted
    assert "教育政策" in formatted
    assert "https://example.com" in formatted


@pytest.mark.asyncio
@patch("agents.government_agent.requests.get")
async def test_government_agent_error_handling(mock_get, government_agent):
    # 接続エラーのシミュレーション
    mock_get.side_effect = Exception("接続エラー")

    response = await government_agent.process("文部科学省の情報を教えて")
    assert isinstance(response, str)
    assert "エラー" in response
