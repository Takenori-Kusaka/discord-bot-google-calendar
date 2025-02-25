import pytest
from agents.kusaka_agent import KusakaAgent

@pytest.fixture
def kusaka_agent():
    return KusakaAgent()

def test_kusaka_agent_initialization(kusaka_agent):
    assert isinstance(kusaka_agent, KusakaAgent)
    assert kusaka_agent.name == "KusakaAgent"
    assert len(kusaka_agent.get_functions()) == 2

@pytest.mark.asyncio
async def test_kusaka_agent_process_all_info(kusaka_agent):
    response = await kusaka_agent.process("日下家について教えて")
    assert isinstance(response, str)
    assert "日下家" in response
    assert "家族構成" in response
    assert "歴史" in response
    assert "伝統" in response
    assert "事業" in response

@pytest.mark.asyncio
async def test_kusaka_agent_process_specific_info(kusaka_agent):
    categories = ["家族構成", "歴史", "伝統", "事業"]
    
    for category in categories:
        response = await kusaka_agent.process(f"日下家の{category}について教えて")
        assert isinstance(response, str)
        assert "日下家" in response
        assert category in response

def test_kusaka_agent_get_info():
    agent = KusakaAgent()
    
    # カテゴリーなしの場合（全情報）
    all_info = agent.get_kusaka_info()
    assert isinstance(all_info, str)
    data = eval(all_info)
    assert len(data) == 4
    assert all(key in data for key in ["家族構成", "歴史", "伝統", "事業"])
    
    # 特定のカテゴリーの場合
    categories = ["家族構成", "歴史", "伝統", "事業"]
    for category in categories:
        info = agent.get_kusaka_info(category)
        assert isinstance(info, str)
        data = eval(info)
        assert "title" in data
        assert "content" in data
        assert category in data["title"]

def test_kusaka_agent_format_info():
    agent = KusakaAgent()
    
    # 単一カテゴリーの情報
    single_info = str({
        "title": "日下家の家族構成",
        "content": "日下家の家族構成に関する情報です（モックデータ）。"
    })
    formatted = agent.format_kusaka_info(single_info)
    assert isinstance(formatted, str)
    assert "日下家の家族構成" in formatted
    
    # 全カテゴリーの情報
    all_info = str({
        "家族構成": {
            "title": "日下家の家族構成",
            "content": "家族構成の情報"
        },
        "歴史": {
            "title": "日下家の歴史",
            "content": "歴史の情報"
        }
    })
    formatted = agent.format_kusaka_info(all_info)
    assert isinstance(formatted, str)
    assert "日下家の家族構成" in formatted
    assert "日下家の歴史" in formatted
