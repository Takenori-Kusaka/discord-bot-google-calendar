#!/usr/bin/env python3
"""イベント検索のデバッグ用テストスクリプト"""

import asyncio
import json
import os
import sys

# プロジェクトのルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def main():
    """イベント検索をテスト"""
    from dotenv import load_dotenv

    load_dotenv()

    # 環境変数を確認
    google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    google_cse_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
    perplexity_api_key = os.getenv("PERPLEXITY_API_KEY", "")
    claude_api_key = os.getenv("ANTHROPIC_API_KEY", "")

    print("=== 環境変数チェック ===")
    print(f"GOOGLE_SEARCH_API_KEY: {'設定済み' if google_api_key else '未設定'}")
    print(f"GOOGLE_SEARCH_ENGINE_ID: {'設定済み' if google_cse_id else '未設定'}")
    print(f"PERPLEXITY_API_KEY: {'設定済み' if perplexity_api_key else '未設定'}")
    print(f"ANTHROPIC_API_KEY: {'設定済み' if claude_api_key else '未設定'}")
    print()

    # EventSearchClientをインポートしてテスト
    from src.clients.event_search import EventSearchClient

    print("=== EventSearchClient テスト ===")
    client = EventSearchClient(
        google_api_key=google_api_key,
        google_search_engine_id=google_cse_id,
        perplexity_api_key=perplexity_api_key,
    )

    print(f"ソース数: {len(client.sources)}")
    for source in client.sources:
        print(f"  - {source.name} ({source.url})")
    print()

    # 検索を実行
    print("=== イベント検索実行中... ===")
    results = await client.search_events()

    print(f"\n=== 検索結果: {len(results)}件 ===")
    for i, result in enumerate(results[:10]):  # 最初の10件を表示
        print(f"\n--- 結果 {i+1} ---")
        print(f"タイトル: {result.get('title', '')[:60]}")
        print(f"スニペット: {result.get('snippet', '')[:100]}")
        print(f"ソース: {result.get('source', '')}")
        print(f"リンク: {result.get('link', '')[:80]}")

    # Claude抽出をテスト
    if results and claude_api_key:
        print("\n\n=== Claude抽出テスト ===")
        from src.clients.claude import ClaudeClient

        claude_client = ClaudeClient(api_key=claude_api_key)

        # 検索結果のテキストを表示
        results_text = "\n\n".join(
            [
                f"【{r.get('query', '')}】\n"
                f"タイトル: {r.get('title', '')}\n"
                f"内容: {r.get('snippet', '')}\n"
                f"URL: {r.get('link', '')}"
                for r in results[:20]  # 最初の20件
            ]
        )
        print("=== Claudeに渡す検索結果テキスト（最初2000文字） ===")
        print(results_text[:2000])
        print("\n...")

        events = await claude_client.extract_events_from_search(results)

        print(f"\n=== 抽出されたイベント: {len(events)}件 ===")
        if events:
            print(json.dumps(events, ensure_ascii=False, indent=2))
        else:
            print("イベントが抽出されませんでした")
    else:
        print("\nClaude抽出テストはスキップ（APIキーなし、または検索結果なし）")


if __name__ == "__main__":
    asyncio.run(main())
