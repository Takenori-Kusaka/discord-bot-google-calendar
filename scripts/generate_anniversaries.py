"""365日分の豆知識データベースを生成するスクリプト

Perplexity APIを使用して、各日に複数の豆知識を収集し、
config/anniversaries.yml に保存します。

使い方:
    python scripts/generate_anniversaries.py

環境変数:
    PERPLEXITY_API_KEY: Perplexity APIキー
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import aiohttp
import yaml

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "config" / "anniversaries.yml"

# 各月の日数
DAYS_IN_MONTH = {
    1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31,
}

SYSTEM_PROMPT = """あなたは博識な日本の執事です。指定された日付の豆知識を3つ提供してください。

以下のカテゴリから多様な情報を選んでください:
- 記念日（日本の記念日、国際デーなど）
- 偉人の誕生日や命日（名言付き）
- 歴史的出来事
- 食べ物の日
- 季節の行事や風習

必ず以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
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
    "quote": "偉人の名言（あれば）"
  },
  {
    "type": "歴史",
    "name": "出来事の名前",
    "description": "出来事の説明。「でございます」調で。"
  }
]"""


async def fetch_anniversary(
    session: aiohttp.ClientSession,
    api_key: str,
    month: int,
    day: int,
) -> list[dict] | None:
    """指定日の豆知識をPerplexity APIで取得"""
    query = f"{month}月{day}日の豆知識を3つ教えてください。記念日、偉人（名言付き）、歴史的出来事などから多様に選んでください。"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    try:
        async with session.post(
            PERPLEXITY_API_URL, headers=headers, json=payload
        ) as response:
            if response.status != 200:
                print(f"  API error for {month}/{day}: status {response.status}")
                return None

            data = await response.json()
            content = data["choices"][0]["message"]["content"]
            return parse_response(content, month, day)

    except Exception as e:
        print(f"  Error for {month}/{day}: {e}")
        return None


def parse_response(content: str, month: int, day: int) -> list[dict] | None:
    """APIレスポンスからJSON配列を抽出してパース"""
    # JSON配列を抽出
    start = content.find("[")
    end = content.rfind("]") + 1
    if start < 0 or end <= start:
        print(f"  No JSON found for {month}/{day}")
        return None

    try:
        items = json.loads(content[start:end])
    except json.JSONDecodeError as e:
        print(f"  JSON parse error for {month}/{day}: {e}")
        return None

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


async def generate_all(api_key: str) -> dict:
    """365日分のデータを生成"""
    # 既存データを読み込み（途中再開用）
    existing = {}
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data and "anniversaries" in data:
                existing = data["anniversaries"]
                print(f"Loaded {len(existing)} existing entries")

    anniversaries = dict(existing)
    total = sum(DAYS_IN_MONTH.values())
    processed = 0

    async with aiohttp.ClientSession() as session:
        for month in range(1, 13):
            for day in range(1, DAYS_IN_MONTH[month] + 1):
                key = f"{month:02d}-{day:02d}"
                processed += 1

                # 既にデータがあればスキップ
                if key in anniversaries:
                    print(f"[{processed}/{total}] {key} - skipped (already exists)")
                    continue

                print(f"[{processed}/{total}] Fetching {key}...")
                items = await fetch_anniversary(session, api_key, month, day)

                if items:
                    anniversaries[key] = items
                    print(f"  Got {len(items)} entries")
                else:
                    print(f"  Failed, will retry later")

                # レート制限対策（1秒待機）
                await asyncio.sleep(1.0)

                # 10日ごとに中間保存
                if processed % 10 == 0:
                    save_data(anniversaries)
                    print(f"  Saved intermediate ({len(anniversaries)} entries)")

    return anniversaries


def save_data(anniversaries: dict) -> None:
    """データをYAMLファイルに保存"""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # キーをソートして保存
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


async def main():
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        # .envファイルから読み込み
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("PERPLEXITY_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    if not api_key:
        print("Error: PERPLEXITY_API_KEY not found")
        print("Set it as an environment variable or in .env file")
        sys.exit(1)

    print("Starting anniversary database generation...")
    print(f"Output: {OUTPUT_PATH}")
    print()

    start_time = time.time()
    anniversaries = await generate_all(api_key)
    save_data(anniversaries)

    elapsed = time.time() - start_time
    print()
    print(f"Done! Generated {len(anniversaries)} entries in {elapsed:.0f}s")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
