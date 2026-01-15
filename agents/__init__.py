"""
Discord bot用のAgent群を提供するパッケージ
各Agentは特定の機能を担当し、ユーザーからのリクエストに応じて適切な情報を提供します。
"""

from .base_agent import BaseAgent
from .calendar_agent import CalendarAgent
from .weather_agent import WeatherAgent
from .search_agent import SearchAgent
from .kusaka_agent import KusakaAgent
from .government_agent import GovernmentAgent
from .news_agent import NewsAgent
from .wikipedia_agent import WikipediaAgent

__all__ = [
    "BaseAgent",
    "CalendarAgent",
    "WeatherAgent",
    "SearchAgent",
    "KusakaAgent",
    "GovernmentAgent",
    "NewsAgent",
    "WikipediaAgent",
]
