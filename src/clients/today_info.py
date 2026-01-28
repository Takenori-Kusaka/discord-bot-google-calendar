"""今日は何の日クライアント

豆知識データベース（YAML）を優先的に使用し、
データがない場合はPerplexity APIで動的に検索します。
"""

import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
import yaml

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TodayInfo:
    """今日は何の日情報"""

    date: datetime
    anniversary: str  # 記念日名
    description: str  # 説明
    trivia: Optional[str] = None  # 豆知識・名言
    source: str = "database"  # "database" or "search"

    def format_for_notification(self) -> str:
        """通知用にフォーマット"""
        lines = [f"本日は「{self.anniversary}」でございます。"]
        if self.description:
            lines.append(self.description)
        if self.trivia:
            lines.append(self.trivia)
        return "\n".join(lines)


class TodayInfoClient:
    """今日は何の日クライアント

    データベース（YAML） → Perplexity API → フォールバック の順で取得します。
    """

    PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

    def __init__(
        self,
        timezone: str = "Asia/Tokyo",
        perplexity_api_key: str | None = None,
        database_path: str | Path | None = None,
    ):
        """初期化

        Args:
            timezone: タイムゾーン
            perplexity_api_key: Perplexity APIキー
            database_path: 豆知識データベースのパス
        """
        self.timezone = timezone
        self.perplexity_api_key = perplexity_api_key

        # データベース読み込み
        if database_path is None:
            database_path = Path("config/anniversaries.yml")
        self._database = self._load_database(Path(database_path))

        logger.info("TodayInfo client initialized")

    def _load_database(self, path: Path) -> dict:
        """YAMLデータベースを読み込む"""
        if not path.exists():
            logger.warning(f"Anniversary database not found: {path}")
            return {}

        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "anniversaries" in data:
                    db = data["anniversaries"]
                    logger.info(f"Loaded {len(db)} anniversary entries")
                    return db
        except Exception as e:
            logger.error(f"Failed to load anniversary database: {e}")

        return {}

    async def get_today_info(self) -> Optional[TodayInfo]:
        """今日は何の日を取得

        Returns:
            TodayInfo: 今日の記念日情報
        """
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(self.timezone))
        month = now.month
        day = now.day

        # 1. データベースから取得（複数候補からランダム選択）
        info = self._get_from_database(month, day, now)
        if info:
            return info

        # 2. Perplexity APIで検索
        if self.perplexity_api_key:
            info = await self._search_today_info(month, day, now)
            if info:
                return info

        # 3. フォールバック
        return TodayInfo(
            date=now,
            anniversary=f"{month}月{day}日",
            description="本日も素敵な一日をお過ごしくださいませ。",
            source="fallback",
        )

    def _get_from_database(
        self, month: int, day: int, now: datetime
    ) -> Optional[TodayInfo]:
        """データベースから豆知識を取得（ランダム選択）"""
        key = f"{month:02d}-{day:02d}"
        entries = self._database.get(key)

        if not entries or not isinstance(entries, list):
            return None

        # 複数の候補からランダムに1つ選択
        entry = random.choice(entries)

        name = entry.get("name", "")
        description = entry.get("description", "")
        quote = entry.get("quote")

        # 名言がある場合はtriviaに設定
        trivia = None
        if quote:
            trivia = quote

        if name:
            return TodayInfo(
                date=now,
                anniversary=name,
                description=description,
                trivia=trivia,
                source="database",
            )

        return None

    async def _search_today_info(
        self, month: int, day: int, now: datetime
    ) -> Optional[TodayInfo]:
        """Perplexity APIで「今日は何の日」を検索"""
        query = f"{month}月{day}日は何の日ですか？日本の記念日や豆知識を1つだけ教えてください。"

        system_prompt = """あなたは博識な執事です。
「今日は何の日」の情報を1つだけ提供してください。

回答形式（必ずこの形式で回答）:
記念日名: （記念日や出来事の名前）
説明: （1〜2文の簡潔な説明。「でございます」調で）

例:
記念日名: 人日の節句
説明: 七草粥を食べて一年の無病息災を願う日でございます。春の七草を入れたお粥で、お正月のご馳走で疲れた胃腸を労わります。"""

        headers = {
            "Authorization": f"Bearer {self.perplexity_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            "temperature": 0.3,
            "max_tokens": 256,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.PERPLEXITY_API_URL, headers=headers, json=payload
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            "Perplexity API error for today info",
                            status=response.status,
                        )
                        return None

                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]
                    return self._parse_search_response(content, now)

        except Exception as e:
            logger.error("Failed to search today info", error=str(e))
            return None

    def _parse_search_response(
        self, content: str, now: datetime
    ) -> Optional[TodayInfo]:
        """Perplexity APIの応答をパース"""
        name = None
        description = None

        for line in content.strip().split("\n"):
            line = line.strip()
            if line.startswith("記念日名:") or line.startswith("記念日名："):
                name = line.split(":", 1)[-1].split("：", 1)[-1].strip()
            elif line.startswith("説明:") or line.startswith("説明："):
                description = line.split(":", 1)[-1].split("：", 1)[-1].strip()

        if name:
            return TodayInfo(
                date=now,
                anniversary=name,
                description=description or "",
                source="search",
            )

        # パースに失敗した場合、レスポンス全体を使う
        if content.strip():
            lines = [l.strip() for l in content.strip().split("\n") if l.strip()]
            if lines:
                return TodayInfo(
                    date=now,
                    anniversary=lines[0][:50],
                    description=" ".join(lines[1:3]) if len(lines) > 1 else "",
                    source="search",
                )

        return None
