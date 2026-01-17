"""地域イベント検索クライアント"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import aiohttp

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RegionalEvent:
    """地域イベント"""

    title: str
    date: str
    location: str
    description: str
    url: Optional[str] = None
    source: str = ""
    target_audience: Optional[str] = None  # 対象年齢層


class EventSearchClient:
    """地域イベント検索クライアント

    Google Search APIとPerplexity APIを使用して
    地域イベント情報を収集します。
    """

    # 検索対象施設・地域
    SEARCH_TARGETS = [
        "高の原イオン イベント",
        "けいはんなプラザ イベント",
        "ミナーラ 奈良 イベント",
        "アスピアやましろ イベント",
        "木津川市 イベント",
        "木津川市 子育て イベント",
        "奈良市 子供 イベント",
        "精華町 イベント",
    ]

    def __init__(
        self,
        google_api_key: str,
        google_search_engine_id: str,
        perplexity_api_key: Optional[str] = None,
        timezone: str = "Asia/Tokyo",
    ):
        self.google_api_key = google_api_key
        self.google_search_engine_id = google_search_engine_id
        self.perplexity_api_key = perplexity_api_key
        self.timezone = ZoneInfo(timezone)

        logger.info(
            "Event search client initialized",
            has_perplexity=bool(perplexity_api_key),
        )

    async def search_events(self) -> list[dict]:
        """地域イベントを検索

        Returns:
            検索結果のリスト
        """
        logger.info("Starting event search")

        results = []

        # Google Custom Search APIで検索
        async with aiohttp.ClientSession() as session:
            for target in self.SEARCH_TARGETS:
                try:
                    search_results = await self._google_search(session, target)
                    results.extend(search_results)
                    # レート制限対策
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Search failed for {target}: {e}")

        logger.info(f"Found {len(results)} raw results from Google Search")

        # Perplexityで補完検索（利用可能な場合）
        if self.perplexity_api_key:
            try:
                perplexity_results = await self._perplexity_search()
                results.extend(perplexity_results)
            except Exception as e:
                logger.warning(f"Perplexity search failed: {e}")

        return results

    async def _google_search(
        self, session: aiohttp.ClientSession, query: str
    ) -> list[dict]:
        """Google Custom Search APIで検索"""
        # 今週末の日付を含めてより具体的に検索
        now = datetime.now(self.timezone)
        weekend = now + timedelta(days=(5 - now.weekday()) % 7)
        date_str = weekend.strftime("%Y年%m月")

        full_query = f"{query} {date_str}"

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.google_api_key,
            "cx": self.google_search_engine_id,
            "q": full_query,
            "num": 5,
            "lr": "lang_ja",
        }

        async with session.get(url, params=params) as response:
            if response.status != 200:
                logger.warning(f"Google Search API error: {response.status}")
                return []

            data = await response.json()
            items = data.get("items", [])

            results = []
            for item in items:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "link": item.get("link", ""),
                        "source": "google_search",
                        "query": query,
                    }
                )

            return results

    async def _perplexity_search(self) -> list[dict]:
        """Perplexity APIで地域イベントを検索"""
        now = datetime.now(self.timezone)
        weekend_start = now + timedelta(days=(5 - now.weekday()) % 7)
        weekend_end = weekend_start + timedelta(days=2)

        prompt = f"""
今週末（{weekend_start.strftime('%m月%d日')}〜{weekend_end.strftime('%m月%d日')}）に
木津川市、奈良市、精華町、高の原周辺で開催されるイベントを教えてください。

特に以下の施設・地域のイベントを重点的に:
- 高の原イオン
- けいはんなプラザ
- ミナーラ
- アスピアやましろ
- 木津川市の公共イベント

子供（0歳〜4歳）連れで参加できるイベントがあれば優先して教えてください。
"""

        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.perplexity_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    logger.warning(f"Perplexity API error: {response.status}")
                    return []

                data = await response.json()
                content = data["choices"][0]["message"]["content"]

                return [
                    {
                        "title": "Perplexity検索結果",
                        "snippet": content,
                        "link": "",
                        "source": "perplexity",
                        "query": "週末イベント総合検索",
                    }
                ]
