"""地域イベント検索クライアント"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import aiohttp
import yaml
from bs4 import BeautifulSoup

from ..utils.logger import get_logger

# Playwright は動的サイト用にオプションでインポート
try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

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


@dataclass
class EventSource:
    """イベントソース設定"""

    name: str
    url: str
    enabled: bool
    priority: int
    selectors: dict
    dynamic: bool = False  # 動的サイト（Vue.js等）フラグ
    wait_time: int = 3  # 動的サイトの描画待機時間（秒）


@dataclass
class ReferenceLink:
    """参考リンク"""

    name: str
    url: str


class EventSearchClient:
    """地域イベント検索クライアント

    Webスクレイピング、Google Search API、Perplexity APIを使用して
    地域イベント情報を収集します。
    """

    # Google Search用のバックアップ検索対象
    SEARCH_TARGETS = [
        "高の原イオン イベント",
        "けいはんなプラザ イベント",
        "木津川市 子育て イベント",
        "奈良市 子供 イベント",
    ]

    def __init__(
        self,
        google_api_key: str,
        google_search_engine_id: str,
        perplexity_api_key: Optional[str] = None,
        timezone: str = "Asia/Tokyo",
        config_path: str = "config/event_sources.yml",
    ):
        self.google_api_key = google_api_key
        self.google_search_engine_id = google_search_engine_id
        self.perplexity_api_key = perplexity_api_key
        self.timezone = ZoneInfo(timezone)
        self.config_path = Path(config_path)

        # 設定を読み込み
        self.sources: list[EventSource] = []
        self.reference_links: list[ReferenceLink] = []
        self.scraping_config: dict = {}
        self.filtering_config: dict = {}
        self._load_config()

        logger.info(
            "Event search client initialized",
            has_perplexity=bool(perplexity_api_key),
            sources_count=len(self.sources),
        )

    def _load_config(self) -> None:
        """設定ファイルを読み込み"""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                # イベントソースを読み込み
                for source_data in config.get("sources", []):
                    if source_data.get("enabled", True):
                        self.sources.append(
                            EventSource(
                                name=source_data["name"],
                                url=source_data["url"],
                                enabled=source_data.get("enabled", True),
                                priority=source_data.get("priority", 5),
                                selectors=source_data.get("selectors", {}),
                                dynamic=source_data.get("dynamic", False),
                                wait_time=source_data.get("wait_time", 3),
                            )
                        )

                # 参考リンクを読み込み
                for link_data in config.get("reference_links", []):
                    self.reference_links.append(
                        ReferenceLink(
                            name=link_data["name"],
                            url=link_data["url"],
                        )
                    )

                # スクレイピング設定
                self.scraping_config = config.get("scraping", {})
                # フィルタリング設定
                self.filtering_config = config.get("filtering", {})

                # 優先度でソート
                self.sources.sort(key=lambda x: x.priority)

                logger.info(f"Loaded {len(self.sources)} event sources from config")
            else:
                logger.warning(f"Config file not found: {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")

    async def search_events(self) -> list[dict]:
        """地域イベントを検索

        Returns:
            検索結果のリスト
        """
        logger.info("Starting event search")

        results = []

        # 1. Webスクレイピングで各サイトからイベントを取得
        scrape_results = await self._scrape_all_sources()
        results.extend(scrape_results)
        logger.info(
            f"Scraped {len(scrape_results)} results from {len(self.sources)} sources"
        )

        # 2. Google Custom Search APIで補完検索
        async with aiohttp.ClientSession() as session:
            for target in self.SEARCH_TARGETS:
                try:
                    search_results = await self._google_search(session, target)
                    results.extend(search_results)
                    # レート制限対策
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Search failed for {target}: {e}")

        logger.info(f"Found {len(results)} total results (scrape + search)")

        # 3. Perplexityで補完検索（利用可能な場合）
        if self.perplexity_api_key:
            try:
                perplexity_results = await self._perplexity_search()
                results.extend(perplexity_results)
            except Exception as e:
                logger.warning(f"Perplexity search failed: {e}")

        # すべて失敗した場合は参考リンクを検索結果として追加
        if not results and self.reference_links:
            for link in self.reference_links:
                results.append(
                    {
                        "title": f"{link.name}（公式）",
                        "snippet": "公式サイトのイベント一覧をご確認ください。",
                        "link": link.url,
                        "source": "reference",
                        "query": link.name,
                    }
                )
            logger.info("Added reference links to search results", count=len(results))

        # フィルタリングと重複排除
        results = self._filter_results(results)
        results = self._dedupe_results(results)

        return results

    async def _scrape_all_sources(self) -> list[dict]:
        """全てのソースからスクレイピング"""
        results = []
        delay = self.scraping_config.get("request_delay", 1.0)
        timeout = self.scraping_config.get("timeout", 30)
        user_agent = self.scraping_config.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )

        headers = {"User-Agent": user_agent}

        async with aiohttp.ClientSession(headers=headers) as session:
            for source in self.sources:
                try:
                    scraped = await self._scrape_source(session, source, timeout)
                    results.extend(scraped)
                    await asyncio.sleep(delay)
                except Exception as e:
                    logger.warning(f"Scrape failed for {source.name}: {e}")

        return results

    async def _scrape_source(
        self,
        session: aiohttp.ClientSession,
        source: EventSource,
        timeout: int,
    ) -> list[dict]:
        """単一ソースからスクレイピング（動的/静的サイト対応）"""
        if source.dynamic:
            # 動的サイト（Vue.js等）はPlaywrightで処理
            return await self._scrape_dynamic_source(source, timeout)
        else:
            # 静的サイトはBeautifulSoupで処理
            return await self._scrape_static_source(source, timeout)

    async def _scrape_static_source(
        self,
        source: EventSource,
        timeout: int,
    ) -> list[dict]:
        """静的サイトからBeautifulSoupでスクレイピング"""
        import ssl

        import certifi

        results = []

        try:
            # SSL証明書の検証を緩和（一部サイト対応）
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as ssl_session:
                async with ssl_session.get(
                    source.url, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            f"HTTP {response.status} for {source.name}: {source.url}"
                        )
                        return []

                    # エンコーディングを自動検出、失敗時はutf-8/shift_jis/euc-jpを試行
                    try:
                        html = await response.text()
                    except UnicodeDecodeError:
                        raw = await response.read()
                        for encoding in ["utf-8", "shift_jis", "euc-jp", "cp932"]:
                            try:
                                html = raw.decode(encoding)
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            html = raw.decode("utf-8", errors="ignore")

                    soup = BeautifulSoup(html, "html.parser")

                    # コンテナセレクタでイベント要素を取得
                    container_selector = source.selectors.get("container", "article")
                    containers = soup.select(container_selector)[:10]  # 最大10件

                    for container in containers:
                        event = self._extract_event_from_element(container, source)
                        if event:
                            results.append(event)

                    logger.info(
                        f"Scraped {len(results)} events from {source.name} (static)"
                    )

        except asyncio.TimeoutError:
            logger.warning(f"Timeout scraping {source.name}")
        except Exception as e:
            logger.warning(f"Error scraping {source.name}: {e}")

        return results

    async def _scrape_dynamic_source(
        self,
        source: EventSource,
        timeout: int,
    ) -> list[dict]:
        """動的サイト（Vue.js等）からPlaywrightでスクレイピング"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(
                f"Playwright not available, skipping dynamic source: {source.name}"
            )
            return []

        results = []

        try:
            async with async_playwright() as p:
                # headlessモードでChromiumを起動
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                try:
                    logger.info(f"Playwright: loading {source.name} ({source.url})")

                    # ページを読み込み
                    await page.goto(
                        source.url,
                        wait_until="load",
                        timeout=timeout * 1000,
                    )

                    # Vue.js等のJSフレームワークがDOMを描画するのを待つ
                    await asyncio.sleep(source.wait_time)

                    # HTMLを取得してBeautifulSoupでパース
                    html_content = await page.content()
                    soup = BeautifulSoup(html_content, "html.parser")

                    # コンテナセレクタでイベント要素を取得
                    container_selector = source.selectors.get("container", "article")
                    containers = soup.select(container_selector)[:10]  # 最大10件

                    for container in containers:
                        event = self._extract_event_from_element(container, source)
                        if event:
                            results.append(event)

                    logger.info(
                        f"Scraped {len(results)} events from {source.name} (dynamic)"
                    )

                finally:
                    await browser.close()

        except asyncio.TimeoutError:
            logger.warning(f"Timeout scraping dynamic source {source.name}")
        except Exception as e:
            logger.warning(f"Error scraping dynamic source {source.name}: {e}")

        return results

    def _extract_event_from_element(
        self, element: BeautifulSoup, source: EventSource
    ) -> Optional[dict]:
        """HTML要素からイベント情報を抽出"""
        try:
            selectors = source.selectors

            # タイトル
            title_elem = element.select_one(selectors.get("title", "h2, h3"))
            title = title_elem.get_text(strip=True) if title_elem else ""

            if not title:
                return None

            # 日付
            date_elem = element.select_one(selectors.get("date", ".date, time"))
            date = date_elem.get_text(strip=True) if date_elem else ""

            # 説明
            desc_elem = element.select_one(selectors.get("description", "p"))
            description = desc_elem.get_text(strip=True)[:200] if desc_elem else ""

            # リンク
            link_elem = element.select_one(selectors.get("link", "a"))
            link = ""
            if link_elem and link_elem.get("href"):
                href = link_elem["href"]
                # 相対URLを絶対URLに変換
                if href.startswith("/"):
                    from urllib.parse import urlparse

                    parsed = urlparse(source.url)
                    link = f"{parsed.scheme}://{parsed.netloc}{href}"
                elif href.startswith("http"):
                    link = href
                else:
                    link = source.url

            return {
                "title": title,
                "snippet": f"{date} - {description}" if date else description,
                "link": link,
                "source": f"scrape:{source.name}",
                "query": source.name,
            }

        except Exception as e:
            logger.debug(f"Failed to extract event: {e}")
            return None

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
- ガーデンモール木津川
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
            "model": "sonar",  # 2025年以降の新モデル名
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

    def get_reference_links(self) -> list[dict]:
        """参考リンクを取得

        Returns:
            参考リンクのリスト [{"name": "...", "url": "..."}]
        """
        return [{"name": link.name, "url": link.url} for link in self.reference_links]

    def format_reference_links(self) -> str:
        """参考リンクを通知用にフォーマット

        Returns:
            フォーマットされた参考リンク文字列
        """
        if not self.reference_links:
            return ""

        lines = ["", "📎 **もっとイベントを探す**"]
        for link in self.reference_links:
            lines.append(f"• [{link.name}]({link.url})")

        return "\n".join(lines)

    def build_fallback_events(
        self, search_results: list[dict], max_events: int = 5
    ) -> list[dict]:
        """抽出失敗時のフォールバック用イベントを生成

        Args:
            search_results: 検索結果
            max_events: 最大件数

        Returns:
            list[dict]: イベント情報リスト
        """
        if not search_results:
            return []

        family_keywords = self.filtering_config.get("family_keywords", [])
        exclude_keywords = self.filtering_config.get("exclude_keywords", [])

        def score(item: dict) -> int:
            text = f"{item.get('title', '')} {item.get('snippet', '')}"
            s = 0
            if any(k in text for k in family_keywords):
                s += 2
            if self._extract_date_from_text(text):
                s += 1
            if any(k in text for k in exclude_keywords):
                s -= 5
            return s

        candidates = [r for r in search_results if score(r) >= 0]
        candidates.sort(key=score, reverse=True)

        events = []
        for r in candidates[:max_events]:
            text = f"{r.get('title', '')} {r.get('snippet', '')}"
            date = self._extract_date_from_text(text) or "今週末（詳細未確認）"
            events.append(
                {
                    "title": r.get("title", "イベント"),
                    "date": date,
                    "location": "",
                    "description": (r.get("snippet", "") or "").strip()[:80],
                    "target_audience": "不明",
                    "url": r.get("link", ""),
                }
            )

        return events

    def build_events_from_results(
        self, search_results: list[dict], max_events: int = 10
    ) -> list[dict]:
        """検索結果からイベント候補を生成（LLM無し）"""
        if not search_results:
            return []

        family_keywords = self.filtering_config.get("family_keywords", [])
        exclude_keywords = self.filtering_config.get("exclude_keywords", [])

        now = datetime.now(self.timezone)

        def score(item: dict) -> int:
            text = f"{item.get('title', '')} {item.get('snippet', '')}"
            s = 0
            if any(k in text for k in family_keywords):
                s += 2
            if self._parse_month_day(text):
                s += 1
            if any(k in text for k in exclude_keywords):
                s -= 5
            return s

        # 除外キーワードでフィルタ
        candidates = []
        for r in search_results:
            text = f"{r.get('title', '')} {r.get('snippet', '')}"
            if any(k in text for k in exclude_keywords):
                continue
            candidates.append(r)

        # 重複排除（タイトル+URL）
        candidates = self._dedupe_results(candidates)
        candidates.sort(key=score, reverse=True)

        events = []
        for r in candidates:
            if len(events) >= max_events:
                break

            text = f"{r.get('title', '')} {r.get('snippet', '')}"
            month_day = self._parse_month_day(text)
            date_label = "今週末（詳細未確認）"
            if month_day:
                month, day = month_day
                try:
                    dt = datetime(now.year, month, day, tzinfo=self.timezone)
                    date_label = dt.strftime("%m/%d")
                except Exception:
                    date_label = f"{month:02d}/{day:02d}"

            audience = "全年齢"
            if any(k in text for k in family_keywords):
                audience = "子供向け"

            events.append(
                {
                    "title": r.get("title", "イベント"),
                    "date": date_label,
                    "location": "",
                    "description": (r.get("snippet", "") or "").strip()[:80],
                    "target_audience": audience,
                    "url": r.get("link", ""),
                }
            )

        return events

    def build_reference_events(self) -> list[dict]:
        """参考リンクから最低限のイベント情報を生成"""
        if not self.reference_links:
            return []

        events = []
        for link in self.reference_links:
            events.append(
                {
                    "title": link.name,
                    "date": "今週末（詳細未確認）",
                    "location": "",
                    "description": "最新情報はリンク先をご確認ください。",
                    "target_audience": "不明",
                    "url": link.url,
                }
            )

        return events

    def _dedupe_results(self, results: list[dict]) -> list[dict]:
        """検索結果の重複排除"""
        seen: set[tuple[str, str]] = set()
        deduped = []
        for r in results:
            key = (r.get("title", ""), r.get("link", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)
        return deduped

    def _filter_results(self, results: list[dict]) -> list[dict]:
        """除外キーワードによるフィルタ"""
        exclude_keywords = self.filtering_config.get("exclude_keywords", [])
        if not exclude_keywords:
            return results

        filtered = []
        for r in results:
            text = f"{r.get('title', '')} {r.get('snippet', '')}"
            if any(k in text for k in exclude_keywords):
                continue
            filtered.append(r)
        return filtered

    def _extract_date_from_text(self, text: str) -> str:
        """テキストから簡易的に日付を抽出"""
        import re

        m = re.search(r"(\d{1,2})月(\d{1,2})日", text)
        if m:
            return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}"
        m = re.search(r"(\d{1,2})/(\d{1,2})", text)
        if m:
            return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}"
        return ""

    def _parse_month_day(self, text: str) -> tuple[int, int] | None:
        """テキストから月日を抽出"""
        import re

        m = re.search(r"(\d{1,2})月(\d{1,2})日", text)
        if m:
            return int(m.group(1)), int(m.group(2))
        m = re.search(r"(\d{1,2})/(\d{1,2})", text)
        if m:
            return int(m.group(1)), int(m.group(2))
        return None
