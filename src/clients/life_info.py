"""生活影響情報クライアント（e-Gov法令API + スクレイピング）"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Optional
from zoneinfo import ZoneInfo

import aiohttp
from bs4 import BeautifulSoup

from ..utils.logger import get_logger

logger = get_logger(__name__)


class TrustLevel(IntEnum):
    """信頼性レベル"""

    UNKNOWN = 1  # 不明・要確認
    SINGLE_SOURCE = 2  # 単一サイト
    NEWS_MAJOR = 3  # 大手ニュース複数
    MULTIPLE_MUNICIPALITIES = 4  # 複数自治体で確認
    OFFICIAL_EGOV = 5  # 官報・e-Gov


TRUST_LABELS = {
    TrustLevel.UNKNOWN: "❓ 要確認",
    TrustLevel.SINGLE_SOURCE: "⚠️ 単一ソース",
    TrustLevel.NEWS_MAJOR: "📰 ニュース確認",
    TrustLevel.MULTIPLE_MUNICIPALITIES: "🏛️ 複数自治体確認",
    TrustLevel.OFFICIAL_EGOV: "📌 官報確認",
}


# 家族に関連するキーワード
FAMILY_KEYWORDS = [
    "児童手当",
    "子育て",
    "保育",
    "幼稚園",
    "育児",
    "出産",
    "妊娠",
    "乳幼児",
    "医療費",
    "予防接種",
    "扶養",
    "所得税",
    "住民税",
    "確定申告",
    "年末調整",
    "住宅ローン",
    "ふるさと納税",
    "社会保険",
    "健康保険",
    "雇用保険",
    "介護",
    "育休",
    "産休",
    "チャイルドシート",
    "道路交通法",
    "教育",
    "給食",
    "学校",
]


@dataclass
class LifeImpactInfo:
    """生活影響情報"""

    title: str
    description: str
    source: str
    source_url: str
    trust_level: TrustLevel
    effective_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    requires_action: bool = False
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(ZoneInfo("Asia/Tokyo"))
    )

    def format_for_notification(self) -> str:
        """通知用にフォーマット"""
        trust_label = TRUST_LABELS.get(self.trust_level, "")
        lines = [f"{trust_label} **{self.title}**", f"  {self.description}"]

        if self.effective_date:
            lines.append(f"  施行日: {self.effective_date.strftime('%Y年%m月%d日')}")

        if self.deadline:
            lines.append(f"  ⏰ 期限: {self.deadline.strftime('%Y年%m月%d日')}")

        if self.requires_action:
            lines.append("  📝 手続きが必要です")

        lines.append(f"  出典: {self.source}")

        return "\n".join(lines)


class LifeInfoClient:
    """生活影響情報クライアント"""

    # e-Gov法令API Version 1のベースURL
    # 参考: https://laws.e-gov.go.jp/docs/law-data-basic/8529371-law-api-v1/
    EGOV_BASE_URL = "https://elaws.e-gov.go.jp/api/1"

    def __init__(self, timezone: str = "Asia/Tokyo"):
        """初期化

        Args:
            timezone: タイムゾーン
        """
        self.timezone = timezone
        logger.info("Life info client initialized")

    async def get_updated_laws(self, days: int = 7) -> list[LifeImpactInfo]:
        """最近の法令更新を取得

        Args:
            days: 何日前からの更新を取得するか

        Returns:
            list[LifeImpactInfo]: 法令更新リスト
        """
        # e-Gov法令API Version 1の法令一覧を取得
        # カテゴリ: 1=全て, 2=憲法・法律, 3=政令・勅令, 4=府省令
        url = f"{self.EGOV_BASE_URL}/lawlists/2"  # 憲法・法律

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        logger.warning(f"e-Gov API error: {response.status}")
                        return []

                    xml_text = await response.text()
                    return self._parse_law_updates(xml_text, days)

        except Exception as e:
            logger.error(f"Failed to fetch law updates: {e}")
            return []

    def _parse_law_updates(
        self, xml_text: str, days: int = 30
    ) -> list[LifeImpactInfo]:
        """XML形式の法令更新をパース

        Args:
            xml_text: XML形式のレスポンス
            days: 何日以内の更新を対象とするか

        Returns:
            list[LifeImpactInfo]: パースされた法令更新リスト
        """
        results = []
        cutoff_date = datetime.now(ZoneInfo(self.timezone)) - timedelta(days=days)

        try:
            root = ET.fromstring(xml_text)

            # 法令情報を抽出（LawNameListInfo構造に対応）
            for law_info in root.findall(".//LawNameListInfo"):
                law_name = law_info.findtext("LawName", "")
                law_no = law_info.findtext("LawNo", "")
                law_id = law_info.findtext("LawId", "")
                promulgation_date = law_info.findtext("PromulgationDate", "")

                # 家族関連のキーワードでフィルタリング
                if not self._is_family_relevant(law_name):
                    continue

                # 施行日をパース
                effective_date = None
                if promulgation_date:
                    try:
                        effective_date = datetime.strptime(
                            promulgation_date, "%Y%m%d"
                        ).replace(tzinfo=ZoneInfo(self.timezone))
                    except ValueError:
                        pass

                # 法令詳細URL
                detail_url = f"https://laws.e-gov.go.jp/law/{law_id}" if law_id else "https://laws.e-gov.go.jp/"

                info = LifeImpactInfo(
                    title=law_name,
                    description=f"法令番号: {law_no}",
                    source="e-Gov法令検索",
                    source_url=detail_url,
                    trust_level=TrustLevel.OFFICIAL_EGOV,
                    effective_date=effective_date,
                )
                results.append(info)

            logger.info(f"Parsed {len(results)} family-relevant laws")

        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")

        return results

    def _is_family_relevant(self, text: str) -> bool:
        """テキストが家族に関連するかチェック

        Args:
            text: チェックするテキスト

        Returns:
            bool: 家族関連であればTrue
        """
        return any(keyword in text for keyword in FAMILY_KEYWORDS)

    async def get_kizugawa_news(self) -> list[LifeImpactInfo]:
        """木津川市の子育て関連ニュースを取得

        Returns:
            list[LifeImpactInfo]: ニュースリスト
        """
        url = "https://www.city.kizugawa.lg.jp/kosodate/"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        logger.warning(f"Kizugawa city site error: {response.status}")
                        return []

                    html = await response.text()
                    return self._parse_kizugawa_news(html, url)

        except Exception as e:
            logger.error(f"Failed to fetch Kizugawa news: {e}")
            return []

    def _parse_kizugawa_news(self, html: str, base_url: str) -> list[LifeImpactInfo]:
        """木津川市サイトのHTMLをパース

        Args:
            html: HTMLテキスト
            base_url: ベースURL

        Returns:
            list[LifeImpactInfo]: パースされたニュースリスト
        """
        results = []
        soup = BeautifulSoup(html, "html.parser")

        # 新着情報セクションを探す
        # 注: 実際のサイト構造に合わせて調整が必要
        news_items = soup.find_all("li", class_="news-item") or soup.find_all(
            "div", class_="news-item"
        )

        # 代替: 一般的なリンクリストを探す
        if not news_items:
            news_section = soup.find("div", class_="news") or soup.find(
                "ul", class_="news-list"
            )
            if news_section:
                news_items = news_section.find_all("li")

        for item in news_items[:10]:  # 最大10件
            link = item.find("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")

            if not title or not self._is_family_relevant(title):
                continue

            # URLを正規化
            if href and not href.startswith("http"):
                href = f"https://www.city.kizugawa.lg.jp{href}"

            info = LifeImpactInfo(
                title=title,
                description="木津川市からのお知らせ",
                source="木津川市",
                source_url=href or base_url,
                trust_level=TrustLevel.MULTIPLE_MUNICIPALITIES,
            )
            results.append(info)

        logger.info(f"Parsed {len(results)} Kizugawa news items")
        return results

    async def get_all_life_info(self) -> list[LifeImpactInfo]:
        """全ての生活影響情報を取得

        Returns:
            list[LifeImpactInfo]: 全情報リスト（信頼性順にソート）
        """
        all_info = []

        # e-Gov法令更新
        law_updates = await self.get_updated_laws()
        all_info.extend(law_updates)

        # 木津川市ニュース
        kizugawa_news = await self.get_kizugawa_news()
        all_info.extend(kizugawa_news)

        # 固定スケジュールの情報
        scheduled_info = self._get_scheduled_info()
        all_info.extend(scheduled_info)

        # 信頼性レベルでソート（高い順）
        all_info.sort(key=lambda x: x.trust_level, reverse=True)

        logger.info(f"Total life info items: {len(all_info)}")
        return all_info

    def _get_scheduled_info(self) -> list[LifeImpactInfo]:
        """固定スケジュールの重要情報を取得

        Returns:
            list[LifeImpactInfo]: 固定スケジュール情報リスト
        """
        now = datetime.now(ZoneInfo(self.timezone))
        results = []

        # 確定申告シーズン（1月中旬〜3月中旬）
        if now.month == 1 and now.day >= 10:
            results.append(
                LifeImpactInfo(
                    title="確定申告の準備を開始しましょう",
                    description="医療費控除、住宅ローン控除、ふるさと納税の書類を準備してください",
                    source="国税庁",
                    source_url="https://www.nta.go.jp/taxes/shiraberu/shinkoku/tokushu/index.htm",
                    trust_level=TrustLevel.OFFICIAL_EGOV,
                    deadline=datetime(now.year, 3, 15, tzinfo=ZoneInfo(self.timezone)),
                    requires_action=True,
                )
            )

        # 年度替わり前（3月）
        if now.month == 3:
            results.append(
                LifeImpactInfo(
                    title="社会保険料率の変更に注意",
                    description="4月から雇用保険料率等が変更される可能性があります",
                    source="厚生労働省",
                    source_url="https://www.mhlw.go.jp/",
                    trust_level=TrustLevel.OFFICIAL_EGOV,
                    effective_date=datetime(
                        now.year, 4, 1, tzinfo=ZoneInfo(self.timezone)
                    ),
                )
            )

        # ふるさと納税リマインダー（11月〜12月）
        if now.month in [11, 12]:
            results.append(
                LifeImpactInfo(
                    title="ふるさと納税の年内寄附を忘れずに",
                    description="今年の控除を受けるには12月31日までに寄附が必要です",
                    source="総務省",
                    source_url="https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/furusato/about/",
                    trust_level=TrustLevel.OFFICIAL_EGOV,
                    deadline=datetime(
                        now.year, 12, 31, tzinfo=ZoneInfo(self.timezone)
                    ),
                    requires_action=True,
                )
            )

        return results

    def format_for_weekly_notification(
        self, info_list: list[LifeImpactInfo]
    ) -> str:
        """週次通知用にフォーマット

        Args:
            info_list: 生活影響情報リスト

        Returns:
            str: フォーマットされた通知文
        """
        if not info_list:
            return "今週は特筆すべき法改正・制度変更の情報はございません。"

        lines = ["【今週の生活影響情報】"]

        for info in info_list[:5]:  # 最大5件
            lines.append("")
            lines.append(info.format_for_notification())

        lines.append("")
        lines.append(
            "※ 詳細は各公式サイトでご確認ください。情報の正確性は保証できません。"
        )

        return "\n".join(lines)
