"""今日は何の日クライアント"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import aiohttp
from bs4 import BeautifulSoup

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TodayInfo:
    """今日は何の日情報"""

    date: datetime
    anniversary: str  # 記念日名
    description: str  # 説明
    trivia: Optional[str] = None  # 豆知識

    def format_for_notification(self) -> str:
        """通知用にフォーマット"""
        lines = [f"本日は「{self.anniversary}」でございます。"]
        if self.description:
            lines.append(self.description)
        return "\n".join(lines)


class TodayInfoClient:
    """今日は何の日クライアント"""

    # Wikipedia「今日は何の日」ページ
    WIKIPEDIA_URL = "https://ja.wikipedia.org/wiki/Wikipedia:%E4%BB%8A%E6%97%A5%E3%81%AF%E4%BD%95%E3%81%AE%E6%97%A5_{month}%E6%9C%88"

    def __init__(self, timezone: str = "Asia/Tokyo"):
        """初期化

        Args:
            timezone: タイムゾーン
        """
        self.timezone = timezone
        logger.info("TodayInfo client initialized")

    async def get_today_info(self) -> Optional[TodayInfo]:
        """今日は何の日を取得

        Returns:
            TodayInfo: 今日の記念日情報
        """
        now = datetime.now(ZoneInfo(self.timezone))
        month = now.month
        day = now.day

        # まず日本の記念日データベースから取得を試みる
        anniversary = self._get_japanese_anniversary(month, day)

        if anniversary:
            return TodayInfo(
                date=now,
                anniversary=anniversary["name"],
                description=anniversary.get("description", ""),
                trivia=anniversary.get("trivia"),
            )

        # フォールバック：汎用的な記念日
        return TodayInfo(
            date=now,
            anniversary=f"{month}月{day}日",
            description="本日も素敵な一日をお過ごしくださいませ。",
        )

    def _get_japanese_anniversary(self, month: int, day: int) -> Optional[dict]:
        """日本の記念日を取得（静的データ）

        Args:
            month: 月
            day: 日

        Returns:
            dict: 記念日情報
        """
        # 主要な記念日データ（拡張可能）
        anniversaries = {
            (1, 1): {
                "name": "元日",
                "description": "新年の始まりでございます。",
            },
            (1, 7): {
                "name": "七草の日",
                "description": "七草粥を食べて無病息災を願う日でございます。",
            },
            (1, 11): {
                "name": "鏡開き",
                "description": "お正月にお供えした鏡餅を食べる日でございます。",
            },
            (2, 3): {
                "name": "節分",
                "description": "豆まきをして邪気を払う日でございます。",
            },
            (2, 14): {
                "name": "バレンタインデー",
                "description": "大切な方へ感謝の気持ちを伝える日でございます。",
            },
            (2, 22): {
                "name": "猫の日",
                "description": "「にゃんにゃんにゃん」の語呂合わせでございます。",
                "trivia": "1987年に制定されました。",
            },
            (3, 3): {
                "name": "ひな祭り",
                "description": "お嬢様の健やかな成長を願う日でございます。",
            },
            (3, 14): {
                "name": "ホワイトデー",
                "description": "バレンタインのお返しをする日でございます。",
            },
            (4, 1): {
                "name": "エイプリルフール",
                "description": "嘘をついても許される日でございます。",
            },
            (4, 29): {
                "name": "昭和の日",
                "description": "昭和天皇の誕生日を記念した祝日でございます。",
            },
            (5, 5): {
                "name": "こどもの日",
                "description": "坊ちゃま、お嬢様の健やかな成長を願う日でございます。",
            },
            (5, 10): {
                "name": "母の日",
                "description": "お母様への感謝を伝える日でございます。",
            },
            (6, 16): {
                "name": "父の日",
                "description": "お父様への感謝を伝える日でございます。",
            },
            (7, 7): {
                "name": "七夕",
                "description": "願い事を短冊に書く日でございます。",
            },
            (8, 11): {
                "name": "山の日",
                "description": "山に親しむ機会を得る日でございます。",
            },
            (9, 15): {
                "name": "敬老の日",
                "description": "お年寄りを敬い、長寿を祝う日でございます。",
            },
            (10, 31): {
                "name": "ハロウィン",
                "description": "仮装を楽しむ日でございます。",
            },
            (11, 3): {
                "name": "文化の日",
                "description": "自由と平和を愛し、文化をすすめる日でございます。",
            },
            (11, 11): {
                "name": "ポッキーの日",
                "description": "1が4つ並ぶ日でございます。",
                "trivia": "江崎グリコが制定しました。",
            },
            (11, 15): {
                "name": "七五三",
                "description": "お子様の成長を祝う日でございます。",
            },
            (11, 22): {
                "name": "いい夫婦の日",
                "description": "「いいふうふ」の語呂合わせでございます。",
            },
            (11, 23): {
                "name": "勤労感謝の日",
                "description": "勤労を尊び、生産を祝う日でございます。",
            },
            (12, 24): {
                "name": "クリスマスイブ",
                "description": "クリスマスの前夜でございます。",
            },
            (12, 25): {
                "name": "クリスマス",
                "description": "家族で過ごす大切な日でございます。",
            },
            (12, 31): {
                "name": "大晦日",
                "description": "一年の終わりの日でございます。",
            },
            # 子供向けの記念日
            (3, 9): {
                "name": "ありがとうの日",
                "description": "「サンキュー」の語呂合わせでございます。",
            },
            (4, 18): {
                "name": "よい歯の日",
                "description": "「よいは」の語呂合わせでございます。歯磨きを忘れずに。",
            },
            (8, 8): {
                "name": "パパの日",
                "description": "「88」で「パパ」と読める日でございます。",
            },
            (10, 4): {
                "name": "いわしの日",
                "description": "「いわし」の語呂合わせでございます。",
            },
            (10, 10): {
                "name": "目の愛護デー",
                "description": "「10 10」を横にすると眉と目に見えることから制定されました。",
            },
        }

        return anniversaries.get((month, day))

    async def get_today_info_with_ai(
        self, claude_client, month: int, day: int
    ) -> Optional[TodayInfo]:
        """AIを使って今日は何の日を取得（拡張用）

        Args:
            claude_client: Claudeクライアント
            month: 月
            day: 日

        Returns:
            TodayInfo: 今日の記念日情報
        """
        # 将来的にClaude APIを使って動的に生成する場合に使用
        pass
