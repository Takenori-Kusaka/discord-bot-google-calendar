"""生活影響情報クライアントの単体テスト"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.clients.life_info import LifeImpactInfo, LifeInfoClient, TrustLevel


class TestLifeImpactInfo:
    """LifeImpactInfoデータクラスのテスト"""

    def _make_info(self, **kwargs):
        """テスト用LifeImpactInfoを作成"""
        defaults = {
            "title": "健康保険法",
            "description": "法令番号: 大正十一年法律第七十号",
            "source": "e-Gov法令検索",
            "source_url": "https://laws.e-gov.go.jp/law/322AC0000000070",
            "trust_level": TrustLevel.OFFICIAL_EGOV,
        }
        defaults.update(kwargs)
        return LifeImpactInfo(**defaults)

    def test_format_basic_without_impact_level(self):
        """impact_levelなしの場合は従来フォーマット"""
        info = self._make_info()
        result = info.format_for_notification()

        assert "📌 官報確認" in result
        assert "健康保険法" in result
        assert "法令番号" in result

    def test_format_enriched_with_impact_level_high(self):
        """impact_level=highの場合は新フォーマット"""
        info = self._make_info(
            impact_level="high",
            description="出産育児一時金の支給額引き上げなど、医療費に関わる改正。",
            family_relevance="育休中の保険料免除に直結します。",
        )
        result = info.format_for_notification()

        assert "🔴 重要" in result
        assert "健康保険法" in result
        assert "出産育児一時金" in result
        assert "👨‍👩‍👧‍👦" in result
        assert "育休中" in result

    def test_format_enriched_with_impact_level_medium(self):
        """impact_level=mediumの場合"""
        info = self._make_info(
            impact_level="medium",
            description="定期接種の対象ワクチン見直し。",
        )
        result = info.format_for_notification()

        assert "🟡 参考" in result

    def test_format_enriched_with_impact_level_low(self):
        """impact_level=lowの場合"""
        info = self._make_info(
            impact_level="low",
            description="組織統合に関する規定整備。",
        )
        result = info.format_for_notification()

        assert "🟢 参考程度" in result

    def test_format_enriched_with_requires_action(self):
        """手続き必要フラグ"""
        info = self._make_info(
            impact_level="high",
            description="確定申告の準備。",
            requires_action=True,
        )
        result = info.format_for_notification()

        assert "📝 手続きが必要です" in result

    def test_format_enriched_with_deadline(self):
        """期限表示"""
        info = self._make_info(
            impact_level="high",
            description="確定申告",
            deadline=datetime(2026, 3, 15, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
        result = info.format_for_notification()

        assert "⏰ 期限: 2026年03月15日" in result

    def test_format_enriched_with_detail_url(self):
        """詳細URL表示"""
        info = self._make_info(
            impact_level="medium",
            description="テスト",
            source_url="https://laws.e-gov.go.jp/law/322AC0000000070",
        )
        result = info.format_for_notification()

        assert "▶ 詳細:" in result
        assert "https://laws.e-gov.go.jp/law/322AC0000000070" in result

    def test_format_enriched_hides_generic_url(self):
        """汎用URLは表示しない"""
        info = self._make_info(
            impact_level="low",
            description="テスト",
            source_url="https://laws.e-gov.go.jp/",
        )
        result = info.format_for_notification()

        assert "▶ 詳細:" not in result


class TestLifeInfoClientFormat:
    """LifeInfoClient のフォーマットテスト"""

    def test_format_for_weekly_notification_empty(self):
        """空リストの場合"""
        client = LifeInfoClient()
        result = client.format_for_weekly_notification([])

        assert "特筆すべき" in result

    def test_format_for_weekly_notification_with_items(self):
        """情報ありの場合"""
        client = LifeInfoClient()
        items = [
            LifeImpactInfo(
                title="健康保険法",
                description="出産育児一時金の改正。",
                source="e-Gov法令検索",
                source_url="https://laws.e-gov.go.jp/law/test",
                trust_level=TrustLevel.OFFICIAL_EGOV,
                impact_level="high",
                family_relevance="育休中の保険料免除に直結。",
            ),
        ]
        result = client.format_for_weekly_notification(items)

        assert "【今週の生活影響情報】" in result
        assert "🔴 重要" in result
        assert "AIの知識に基づく要約です" in result

    def test_format_for_weekly_notification_max_5_items(self):
        """最大5件まで"""
        client = LifeInfoClient()
        items = [
            LifeImpactInfo(
                title=f"法令{i}",
                description=f"説明{i}",
                source="テスト",
                source_url="https://example.com",
                trust_level=TrustLevel.OFFICIAL_EGOV,
                impact_level="low",
            )
            for i in range(10)
        ]
        result = client.format_for_weekly_notification(items)

        # 6件目以降は含まれない
        assert "法令0" in result
        assert "法令4" in result
        assert "法令5" not in result


class TestLifeInfoClientFamilyRelevance:
    """家族関連キーワードフィルタのテスト"""

    def test_family_relevant_keywords(self):
        """家族関連キーワードが正しくマッチ"""
        client = LifeInfoClient()
        assert client._is_family_relevant("児童手当法") is True
        assert client._is_family_relevant("健康保険法") is True
        assert client._is_family_relevant("予防接種法") is True

    def test_non_family_relevant(self):
        """無関係な法令はマッチしない"""
        client = LifeInfoClient()
        assert client._is_family_relevant("電波法") is False
        assert client._is_family_relevant("著作権法") is False
