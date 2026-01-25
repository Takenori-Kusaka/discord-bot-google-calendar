"""週次イベント通知の仮実行スクリプト

実際のAPIを使用して、イベント検索→Claude抽出→メッセージ生成までをテストします。
Discordへの送信は行わず、結果を表示します。
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

async def main():
    print("=" * 60)
    print("週次イベント通知 仮実行テスト")
    print(f"実行日時: {datetime.now(ZoneInfo('Asia/Tokyo'))}")
    print("=" * 60)
    
    # 設定を読み込み
    from src.config.settings import get_settings
    settings = get_settings()
    
    print(f"\n[設定確認]")
    print(f"  - タイムゾーン: {settings.timezone}")
    print(f"  - 地域チャンネル: {settings.discord_channel_region}")
    
    # EventSearchClientを初期化
    from src.clients.event_search import EventSearchClient
    
    event_search = EventSearchClient(
        google_api_key=settings.google_search_api_key,
        google_search_engine_id=settings.google_search_engine_id,
        perplexity_api_key=getattr(settings, 'perplexity_api_key', None),
        timezone=settings.timezone,
    )
    
    print(f"\n[Step 1] 地域イベントを検索中...")
    search_results = await event_search.search_events()
    print(f"  → 検索結果: {len(search_results)}件")
    
    if search_results:
        print(f"\n  検索結果サンプル（最大5件）:")
        for i, result in enumerate(search_results[:5], 1):
            title = result.get('title', '不明')[:50]
            source = result.get('source', '不明')
            print(f"    {i}. {title} (source: {source})")
    else:
        print("  ⚠️ 検索結果が0件です！")
    
    # ClaudeClientを初期化
    from src.clients.claude import ClaudeClient
    
    claude = ClaudeClient(
        api_key=settings.anthropic_api_key,
        model=settings.claude_model,
    )
    
    print(f"\n[Step 2] 検索結果からイベント情報を抽出中...")
    events = await claude.extract_events_from_search(search_results)
    print(f"  → 抽出されたイベント: {len(events)}件")
    
    if events:
        print(f"\n  抽出イベントサンプル（最大5件）:")
        for i, event in enumerate(events[:5], 1):
            title = event.get('title', '不明')
            date = event.get('date', '不明')
            print(f"    {i}. {title} ({date})")
    else:
        print("  ⚠️ Claude抽出結果が0件です！")
        
        # フォールバック処理
        print(f"\n[Step 2b] フォールバック: 検索結果からイベントを構築...")
        if search_results:
            events = event_search.build_events_from_results(search_results)
            print(f"  → 構築されたイベント: {len(events)}件")
        
        if not events:
            print(f"\n[Step 2c] 参考イベントを生成...")
            events = event_search.build_reference_events()
            print(f"  → 参考イベント: {len(events)}件")
    
    print(f"\n[Step 3] 家族向けおすすめメッセージを生成中...")
    message = await claude.generate_event_recommendation(
        events,
        butler_name="黒田",
    )
    
    # 参考リンクを追加
    reference_links = event_search.format_reference_links()
    if reference_links:
        message = message + reference_links
    
    print(f"\n" + "=" * 60)
    print("生成されたメッセージ:")
    print("=" * 60)
    print(message)
    print("=" * 60)
    
    print(f"\n[結果サマリー]")
    print(f"  - 検索結果: {len(search_results)}件")
    print(f"  - 抽出イベント: {len(events)}件")
    print(f"  - メッセージ長: {len(message)}文字")
    
    # 問題の診断
    print(f"\n[診断]")
    if len(search_results) == 0:
        print("  ❌ 問題: 検索結果が0件 → スクレイピング/APIに問題がある可能性")
    elif len(events) == 0:
        print("  ❌ 問題: イベント抽出が0件 → Claude抽出に問題がある可能性")
    elif "お知らせできる情報が見つかりませんでした" in message:
        print("  ❌ 問題: メッセージに「見つかりませんでした」が含まれている")
    else:
        print("  ✅ 正常: イベント情報が取得・抽出・メッセージ生成されました")

if __name__ == "__main__":
    asyncio.run(main())
