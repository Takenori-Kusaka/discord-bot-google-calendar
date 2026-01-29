"""365日分の豆知識データベースを生成するスクリプト

Google Custom Search APIで検索し、Claude APIで構造化して
config/anniversaries.yml に保存します。

使い方:
    # 試験実行（3日分）
    python scripts/generate_anniversaries.py --start 01-29 --end 01-31

    # 1月分を生成
    python scripts/generate_anniversaries.py --start 01-01 --end 01-31

    # 全日分を生成（API制限に注意: 100回/日）
    python scripts/generate_anniversaries.py

環境変数:
    GOOGLE_SEARCH_API_KEY: Google Custom Search APIキー
    GOOGLE_SEARCH_ENGINE_ID: Google Custom Search Engine ID
    ANTHROPIC_API_KEY: Anthropic APIキー
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import aiohttp
import anthropic
import yaml

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_PATH = PROJECT_ROOT / "config" / "anniversaries.yml"

# 各月の日数
DAYS_IN_MONTH = {
    1: 31,
    2: 29,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31,
}

GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# 1日あたり3クエリで全カテゴリを網羅
QUERY_TEMPLATES = [
    "{month}月{day}日 記念日 何の日 歴史 出来事",
    "{month}月{day}日 偉人 誕生日 命日 名言",
    "{month}月{day}日 豆知識 雑学 食べ物の日 行事",
]

CLAUDE_SYSTEM_PROMPT = """あなたは博識な日本の執事「黒田」です。
与えられたGoogle検索結果を基に、指定された日付の豆知識を5つ作成してください。

## 出力カテゴリ（以下から多様に選択）
- 記念日: 日本の記念日、世界の記念日、食べ物の日
- 偉人: 偉人の誕生日・命日（名言付き）
- 歴史: その日に起きた歴史的出来事
- ことわざ: 日本のことわざ・四字熟語
- 健康: 季節に合った健康アドバイス
- 文化: 行事食・年中行事・郷土文化
- 雑学: 面白い豆知識

## 出力形式
必ず以下のJSON配列で回答してください。JSON以外のテキストは含めないでください。

```json
[
  {
    "type": "記念日",
    "name": "記念日の名前",
    "description": "1〜2文の説明。「でございます」調で。"
  },
  {
    "type": "偉人",
    "name": "偉人の名前（誕生日/命日）",
    "description": "偉人の説明。「でございます」調で。",
    "quote": "「偉人の名言」"
  }
]
```

## 注意事項
- descriptionは必ず「でございます」「ございます」調の執事口調で書く
- 偉人カテゴリには可能な限りquote（名言）を含める
- 検索結果に含まれない情報は、あなたの知識で補完してよい
- 各エントリは独立して読める内容にする
- 5つのエントリは異なるカテゴリから選ぶ"""


def load_env():
    """環境変数を.envファイルから読み込む"""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = value


async def google_search(
    session: aiohttp.ClientSession,
    api_key: str,
    engine_id: str,
    query: str,
) -> list[dict]:
    """Google Custom Search APIで検索"""
    params = {
        "key": api_key,
        "cx": engine_id,
        "q": query,
        "num": 5,
        "lr": "lang_ja",
    }

    try:
        async with session.get(GOOGLE_SEARCH_URL, params=params) as response:
            if response.status != 200:
                error = await response.text()
                print(f"  Google API error ({response.status}): {error[:200]}")
                return []

            data = await response.json()
            items = data.get("items", [])
            return [
                {
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                }
                for item in items
            ]
    except Exception as e:
        print(f"  Google search error: {e}")
        return []


def structure_with_claude(
    claude_client: anthropic.Anthropic,
    month: int,
    day: int,
    search_results: list[dict],
) -> list[dict] | None:
    """Claude APIで検索結果を構造化"""
    # 検索結果をテキストにまとめる
    results_text = "\n\n".join(
        f"【{r['title']}】\n{r['snippet']}" for r in search_results
    )

    user_prompt = f"""{month}月{day}日の豆知識を5つ作成してください。

## Google検索結果
{results_text}

上記の検索結果を参考に、{month}月{day}日に関する豆知識を5つ、JSON配列で出力してください。"""

    try:
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=CLAUDE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text

        # JSON配列を抽出
        start = content.find("[")
        end = content.rfind("]") + 1
        if start < 0 or end <= start:
            print(f"  No JSON found in Claude response")
            return None

        items = json.loads(content[start:end])

        # バリデーション
        valid_items = []
        for item in items:
            if isinstance(item, dict) and "name" in item and "description" in item:
                entry = {
                    "type": item.get("type", "記念日"),
                    "name": item["name"],
                    "description": item["description"],
                }
                if item.get("quote"):
                    entry["quote"] = item["quote"]
                valid_items.append(entry)

        return valid_items if valid_items else None

    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  Claude API error: {e}")
        return None


def load_existing_data() -> dict:
    """既存データを読み込み（途中再開用）"""
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data and "anniversaries" in data:
                return data["anniversaries"]
    return {}


def save_data(anniversaries: dict) -> None:
    """データをYAMLファイルに保存"""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    sorted_data = dict(sorted(anniversaries.items()))
    output = {"anniversaries": sorted_data}

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        yaml.dump(
            output,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )


def parse_date_arg(date_str: str) -> tuple[int, int]:
    """MM-DD形式の文字列を(month, day)に変換"""
    parts = date_str.split("-")
    return int(parts[0]), int(parts[1])


def generate_date_range(
    start: tuple[int, int] | None, end: tuple[int, int] | None
) -> list[tuple[int, int]]:
    """日付範囲を生成"""
    dates = []
    for month in range(1, 13):
        for day in range(1, DAYS_IN_MONTH[month] + 1):
            if start and (month, day) < start:
                continue
            if end and (month, day) > end:
                continue
            dates.append((month, day))
    return dates


async def process_date(
    session: aiohttp.ClientSession,
    google_api_key: str,
    google_engine_id: str,
    claude_client: anthropic.Anthropic,
    month: int,
    day: int,
) -> list[dict] | None:
    """1日分のデータを生成"""
    # Google検索（3クエリ）
    all_results = []
    for template in QUERY_TEMPLATES:
        query = template.format(month=month, day=day)
        results = await google_search(session, google_api_key, google_engine_id, query)
        all_results.extend(results)
        # レート制限対策
        await asyncio.sleep(0.5)

    if not all_results:
        print(f"  No search results")
        return None

    # Claude APIで構造化
    entries = structure_with_claude(claude_client, month, day, all_results)
    return entries


async def main():
    load_env()

    parser = argparse.ArgumentParser(description="365日分の豆知識データベースを生成")
    parser.add_argument("--start", type=str, help="開始日（MM-DD形式）", default=None)
    parser.add_argument("--end", type=str, help="終了日（MM-DD形式）", default=None)
    parser.add_argument("--dry-run", action="store_true", help="実行せずに対象日を表示")
    args = parser.parse_args()

    # API キー取得
    google_api_key = os.environ.get("GOOGLE_SEARCH_API_KEY")
    google_engine_id = os.environ.get("GOOGLE_SEARCH_ENGINE_ID")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not google_api_key or not google_engine_id:
        print("Error: GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID are required")
        sys.exit(1)

    if not anthropic_api_key:
        print("Error: ANTHROPIC_API_KEY is required")
        sys.exit(1)

    # 日付範囲
    start = parse_date_arg(args.start) if args.start else None
    end = parse_date_arg(args.end) if args.end else None
    dates = generate_date_range(start, end)

    print(f"Target: {len(dates)} days")
    print(f"Google API calls: {len(dates) * 3}")
    print(f"Claude API calls: {len(dates)}")
    print(f"Output: {OUTPUT_PATH}")
    print()

    if args.dry_run:
        for m, d in dates:
            print(f"  {m:02d}-{d:02d}")
        return

    # 既存データ読み込み
    anniversaries = load_existing_data()
    print(f"Existing entries: {len(anniversaries)}")

    # Claude クライアント初期化
    claude_client = anthropic.Anthropic(api_key=anthropic_api_key)

    # 処理
    start_time = time.time()
    processed = 0
    skipped = 0
    failed = 0

    async with aiohttp.ClientSession() as session:
        for month, day in dates:
            key = f"{month:02d}-{day:02d}"
            processed += 1

            # 既にデータがあればスキップ
            if key in anniversaries:
                skipped += 1
                print(f"[{processed}/{len(dates)}] {key} - skipped")
                continue

            print(f"[{processed}/{len(dates)}] Processing {key}...")
            entries = await process_date(
                session,
                google_api_key,
                google_engine_id,
                claude_client,
                month,
                day,
            )

            if entries:
                anniversaries[key] = entries
                print(f"  Got {len(entries)} entries")
            else:
                failed += 1
                print(f"  Failed")

            # 10日ごとに中間保存
            if processed % 10 == 0:
                save_data(anniversaries)
                print(f"  [Saved: {len(anniversaries)} entries]")

            # レート制限対策（Google API: 100/日なので慎重に）
            await asyncio.sleep(1.0)

    # 最終保存
    save_data(anniversaries)

    elapsed = time.time() - start_time
    print()
    print(f"Done! {len(anniversaries)} entries in {elapsed:.0f}s")
    print(f"  Processed: {processed - skipped}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
