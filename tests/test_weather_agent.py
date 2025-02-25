import pytest
from agents.weather_agent import WeatherAgent

@pytest.fixture
def weather_agent():
    return WeatherAgent()

def test_weather_agent_initialization(weather_agent):
    assert isinstance(weather_agent, WeatherAgent)
    assert weather_agent.name == "WeatherAgent"
    assert len(weather_agent.get_functions()) == 2

@pytest.mark.asyncio
async def test_weather_agent_process(weather_agent):
    response = await weather_agent.process("今日の天気は？")
    assert isinstance(response, str)
    assert "天気予報" in response
