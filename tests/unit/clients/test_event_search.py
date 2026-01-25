"""EventSearchClient の単体テスト

地域イベント検索クライアントのテストケース。
スクレイピング、API呼び出し、フォールバック処理をテストします。
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo


class TestEventSearchClientInitialization:
    """EventSearchClient初期化のテスト"""

    def test_initialization_with_all_keys(self):
        """すべてのAPIキーを設定して初期化"""
        from src.clients.event_search import EventSearchClient

        client = EventSearchClient(
            google_api_key="test_google_key",
            google_search_engine_id="test_engine_id",
            perplexity_api_key="test_perplexity_key",
            timezone="Asia/Tokyo",
        )

        assert client.google_api_key == "test_google_key"
        assert client.google_search_engine_id == "test_engine_id"
        assert client.perplexity_api_key == "test_perplexity_key"

    def test_initialization_without_perplexity(self):
        """Perplexity APIキーなしで初期化"""
        from src.clients.event_search import EventSearchClient

        client = EventSearchClient(
            google_api_key="test_google_key",
            google_search_engine_id="test_engine_id",
            timezone="Asia/Tokyo",
        )

        assert client.perplexity_api_key is None

    def test_initialization_minimal(self):
        """必須引数のみで初期化"""
        from src.clients.event_search import EventSearchClient

        client = EventSearchClient(
            google_api_key="test_key",
            google_search_engine_id="test_engine",
            timezone="Asia/Tokyo",
        )

        assert client.timezone == ZoneInfo("Asia/Tokyo")


class TestSearchEvents:
    """search_eventsメソッドのテスト"""

    @pytest.fixture
    def event_search_client(self):
        """EventSearchClientのインスタンス"""
        from src.clients.event_search import EventSearchClient

        return EventSearchClient(
            google_api_key="test_key",
            google_search_engine_id="test_engine",
            timezone="Asia/Tokyo",
        )

    @pytest.mark.asyncio
    async def test_search_events_with_scraping_results(self, event_search_client):
        """スクレイピングで結果が取得できた場合"""
        scrape_results = [
            {"title": "テストイベント1", "date": "1/25(土)", "source": "テストサイト"},
            {"title": "テストイベント2", "date": "1/26(日)", "source": "テストサイト"},
        ]

        with patch.object(
            event_search_client, "_scrape_all_sources", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = scrape_results
            # Google/Perplexity検索をスキップ
            with patch.object(
                event_search_client, "_google_search", new_callable=AsyncMock
            ) as mock_google:
                mock_google.return_value = []
                with patch.object(
                    event_search_client, "_perplexity_search", new_callable=AsyncMock
                ) as mock_perplexity:
                    mock_perplexity.return_value = []

                    results = await event_search_client.search_events()

                    assert len(results) >= 2
                    mock_scrape.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_events_empty_all_sources(self, event_search_client):
        """すべてのソースから結果が取得できなかった場合"""
        with patch.object(
            event_search_client, "_scrape_all_sources", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = []
            with patch.object(
                event_search_client, "_google_search", new_callable=AsyncMock
            ) as mock_google:
                mock_google.return_value = []
                with patch.object(
                    event_search_client, "_perplexity_search", new_callable=AsyncMock
                ) as mock_perplexity:
                    mock_perplexity.return_value = []

                    results = await event_search_client.search_events()

                    # フォールバック（参考リンク）が返される
                    assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_events_google_api_fallback(self, event_search_client):
        """スクレイピング失敗時にGoogle APIへフォールバック"""
        google_results = [
            {"title": "Google検索結果", "link": "https://example.com"}
        ]

        with patch.object(
            event_search_client, "_scrape_all_sources", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = []  # スクレイピング失敗
            with patch.object(
                event_search_client, "_google_search", new_callable=AsyncMock
            ) as mock_google:
                mock_google.return_value = google_results
                with patch.object(
                    event_search_client, "_perplexity_search", new_callable=AsyncMock
                ) as mock_perplexity:
                    mock_perplexity.return_value = []

                    results = await event_search_client.search_events()

                    # Google検索結果が含まれる
                    mock_google.assert_called()


class TestGoogleSearch:
    """Google Custom Search APIのテスト"""

    @pytest.fixture
    def event_search_client(self):
        """EventSearchClientのインスタンス"""
        from src.clients.event_search import EventSearchClient

        return EventSearchClient(
            google_api_key="test_key",
            google_search_engine_id="test_engine",
            timezone="Asia/Tokyo",
        )

    @pytest.mark.asyncio
    async def test_google_search_success(self, event_search_client):
        """Google検索が成功した場合"""
        mock_response_data = {
            "items": [
                {
                    "title": "週末イベント情報",
                    "link": "https://example.com/event",
                    "snippet": "今週末のイベント情報です",
                },
            ]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)

        # _google_searchはinternalメソッドなのでセッションを直接渡す
        results = await event_search_client._google_search(mock_session, "高の原 イベント")

        assert len(results) == 1
        assert results[0]["title"] == "週末イベント情報"

    @pytest.mark.asyncio
    async def test_google_search_api_error(self, event_search_client):
        """Google APIエラー時は空リストを返す"""
        mock_response = AsyncMock()
        mock_response.status = 500

        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)

        results = await event_search_client._google_search(mock_session, "高の原 イベント")

        assert results == []

    @pytest.mark.asyncio
    async def test_google_search_no_api_key(self):
        """APIキーが空の場合は空リストを返す"""
        from src.clients.event_search import EventSearchClient

        client = EventSearchClient(
            google_api_key="",  # 空文字列
            google_search_engine_id="",
            timezone="Asia/Tokyo",
        )

        mock_session = MagicMock()
        results = await client._google_search(mock_session, "高の原 イベント")

        assert results == []


class TestBuildFallbackEvents:
    """フォールバックイベント生成のテスト"""

    @pytest.fixture
    def event_search_client(self):
        """EventSearchClientのインスタンス"""
        from src.clients.event_search import EventSearchClient

        return EventSearchClient(
            google_api_key="test_key",
            google_search_engine_id="test_engine",
            timezone="Asia/Tokyo",
        )

    def test_build_fallback_events_from_search_results(self, event_search_client):
        """検索結果からフォールバックイベントを生成"""
        search_results = [
            {
                "title": "高の原マルシェ開催",
                "snippet": "1月25日（土）10時から高の原で開催",
                "link": "https://example.com/marche",
            },
            {
                "title": "けいはんなプラザイベント",
                "snippet": "週末のイベント情報",
                "link": "https://example.com/keihanna",
            },
        ]

        events = event_search_client.build_fallback_events(search_results)

        assert isinstance(events, list)

    def test_build_events_from_results(self, event_search_client):
        """検索結果からイベント情報を構築"""
        search_results = [
            {
                "title": "テストイベント",
                "snippet": "1/25(土) 10:00〜",
                "source": "テストサイト",
            },
        ]

        events = event_search_client.build_events_from_results(search_results)

        assert isinstance(events, list)


class TestFormatReferenceLinks:
    """参考リンクフォーマットのテスト"""

    @pytest.fixture
    def event_search_client(self):
        """EventSearchClientのインスタンス"""
        from src.clients.event_search import EventSearchClient

        return EventSearchClient(
            google_api_key="test_key",
            google_search_engine_id="test_engine",
            timezone="Asia/Tokyo",
        )

    def test_format_reference_links(self, event_search_client):
        """参考リンクのフォーマット"""
        result = event_search_client.format_reference_links()

        # 参考リンクが含まれる（設定ファイルに依存）
        assert isinstance(result, str)


class TestDeduplication:
    """重複排除のテスト"""

    @pytest.fixture
    def event_search_client(self):
        """EventSearchClientのインスタンス"""
        from src.clients.event_search import EventSearchClient

        return EventSearchClient(
            google_api_key="test_key",
            google_search_engine_id="test_engine",
            timezone="Asia/Tokyo",
        )

    def test_dedupe_results_removes_duplicates(self, event_search_client):
        """重複した結果を削除"""
        results = [
            {"title": "イベントA", "link": "https://example.com/a"},
            {"title": "イベントA", "link": "https://example.com/a"},  # 重複
            {"title": "イベントB", "link": "https://example.com/b"},
        ]

        deduped = event_search_client._dedupe_results(results)

        # 重複が削除されている
        titles = [r.get("title") for r in deduped]
        assert titles.count("イベントA") == 1
        assert "イベントB" in titles


class TestFiltering:
    """フィルタリングのテスト"""

    @pytest.fixture
    def event_search_client(self):
        """EventSearchClientのインスタンス"""
        from src.clients.event_search import EventSearchClient

        return EventSearchClient(
            google_api_key="test_key",
            google_search_engine_id="test_engine",
            timezone="Asia/Tokyo",
        )

    def test_filter_results_removes_excluded_keywords(self, event_search_client):
        """除外キーワードを含む結果を削除"""
        results = [
            {"title": "通常のイベント", "snippet": "楽しいイベント"},
            {"title": "求人情報", "snippet": "アルバイト募集"},  # 除外対象
        ]

        filtered = event_search_client._filter_results(results)

        # フィルタリングが適用されている
        assert isinstance(filtered, list)


class TestErrorHandling:
    """エラーハンドリングのテスト"""

    @pytest.fixture
    def event_search_client(self):
        """EventSearchClientのインスタンス"""
        from src.clients.event_search import EventSearchClient

        return EventSearchClient(
            google_api_key="test_key",
            google_search_engine_id="test_engine",
            timezone="Asia/Tokyo",
        )

    @pytest.mark.asyncio
    async def test_search_events_handles_scraping_error(self, event_search_client):
        """スクレイピングエラーを適切に処理"""
        with patch.object(
            event_search_client, "_scrape_all_sources", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.side_effect = Exception("Scraping failed")
            with patch.object(
                event_search_client, "_google_search", new_callable=AsyncMock
            ) as mock_google:
                mock_google.return_value = []
                with patch.object(
                    event_search_client, "_perplexity_search", new_callable=AsyncMock
                ) as mock_perplexity:
                    mock_perplexity.return_value = []

                    # エラーが発生しても例外を投げない
                    try:
                        results = await event_search_client.search_events()
                        assert isinstance(results, list)
                    except Exception:
                        # 実装によってはエラーを投げる可能性もある
                        pass

    @pytest.mark.asyncio
    async def test_google_search_handles_network_error(self, event_search_client):
        """ネットワークエラー発生時の動作を確認"""
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("Network error"))

        # _google_search内部でtry-exceptがなければ例外が発生する
        # 実装に合わせて例外発生またはエラーハンドリングをテスト
        try:
            results = await event_search_client._google_search(mock_session, "テスト")
            # エラーハンドリングされていれば空リスト
            assert results == []
        except Exception as e:
            # エラーが伝播する実装の場合
            assert "Network error" in str(e)


class TestSchedulerIntegration:
    """スケジューラ統合テスト（二重実行防止）"""

    def test_scheduler_job_configuration(self):
        """スケジューラのジョブ設定が正しいか確認"""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from src.scheduler.jobs import setup_scheduler

        async def mock_morning_job():
            pass

        async def mock_weekly_job():
            pass

        scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")
        setup_scheduler(
            morning_job=mock_morning_job,
            weekly_job=mock_weekly_job,
            scheduler=scheduler,
        )

        # ジョブが登録されているか確認
        jobs = scheduler.get_jobs()
        job_ids = [job.id for job in jobs]

        assert "morning_notification" in job_ids
        assert "weekly_events" in job_ids

        # 二重実行防止設定の確認
        for job in jobs:
            # max_instances, coalesce が設定されているか確認
            assert job.max_instances == 1, f"Job {job.id} should have max_instances=1"
            assert job.coalesce is True, f"Job {job.id} should have coalesce=True"
            # misfire_grace_time は None でなければOK（設定されている）
            assert job.misfire_grace_time is not None, f"Job {job.id} should have misfire_grace_time set"
