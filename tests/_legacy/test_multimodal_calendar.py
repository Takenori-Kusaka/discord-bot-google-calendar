import os
import base64
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import asyncio
import anthropic
from dotenv import load_dotenv
from agents.calendar_agent import add_event

load_dotenv()

def encode_image_to_base64(image_path):
    """画像ファイルをbase64エンコードする"""
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def fix_json_format(json_str: str) -> str:
    """JSONの形式を修正する"""
    # 改行とスペースの正規化
    lines = [line.strip() for line in json_str.splitlines()]
    # 各行の末尾にカンマを追加（必要な場合）
    for i in range(len(lines) - 1):
        line = lines[i]
        next_line = lines[i + 1]
        if (
            line and
            not line.endswith(',') and
            not line.endswith('{') and
            not line.endswith('[') and
            not next_line.startswith('}') and
            not next_line.startswith(']')
        ):
            lines[i] = line + ','
    return '\n'.join(lines)

async def process_image_calendar_request(image_path: str) -> str:
    """画像から予定情報を抽出してカレンダーに登録する"""
    try:
        # 画像をbase64エンコード
        image_base64 = encode_image_to_base64(image_path)
        
        # Anthropicクライアントの初期化
        client = anthropic.Client(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # システムプロンプト
        system_prompt = """
あなたは画像から予定情報を抽出する日本のカレンダーアシスタントです。
以下の形式で予定情報を出力してください。
必ず以下の例のように、各フィールドをカンマで区切った有効なJSON形式で出力してください：

例：
{
    "title": "イベント名",
    "date_info": {
        "year": 2025,
        "month": 1,
        "day": 1
    },
    "time_info": {
        "start_hour": 10,
        "start_minute": 0,
        "duration_hours": 2,
        "end_hour": null
    },
    "location": {
        "name": "会場名",
        "address": "住所",
        "notes": "アクセス情報"
    },
    "description": "イベントの説明",
    "event_type": "イベントの種類"
}

上記の形式に従って、画像から抽出した情報を出力してください。
各フィールドの末尾には必ずカンマを付け、最後のフィールドにはカンマを付けないでください。
読み取れない情報は必ずnullと設定してください。
"""

        # Anthropic APIを呼び出し
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": system_prompt
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_base64
                        }
                    }
                ]
            }],
            max_tokens=1000
        )

        # レスポンスの解析
        response_text = response.content[0].text.strip()
        print(f"APIレスポンス:\n{response_text}")
        
        # JSON部分の抽出とパース
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start == -1 or json_end == 0:
            raise ValueError("APIレスポンスからJSONが見つかりません")
        
        json_str = response_text[json_start:json_end]
        print(f"\n抽出されたJSON:\n{json_str}")
        
        # JSON形式の修正とパース
        try:
            fixed_json = fix_json_format(json_str)
            print(f"\n修正後のJSON:\n{fixed_json}")
            parsed_info = json.loads(fixed_json)
        except json.JSONDecodeError as e:
            print(f"JSONパースエラー: {str(e)}")
            # バックアップとしてeval
            import ast
            fixed_json = fixed_json.replace('null', 'None')
            parsed_info = ast.literal_eval(fixed_json)

        # 日時の設定
        start_time = datetime(
            year=parsed_info["date_info"].get("year", datetime.now().year),
            month=parsed_info["date_info"].get("month", datetime.now().month),
            day=parsed_info["date_info"].get("day", datetime.now().day),
            hour=parsed_info["time_info"].get("start_hour", 10),
            minute=parsed_info["time_info"].get("start_minute", 0),
            tzinfo=ZoneInfo("Asia/Tokyo")
        )

        # 終了時刻の計算
        if parsed_info["time_info"].get("end_hour"):
            end_time = start_time.replace(hour=parsed_info["time_info"]["end_hour"])
        elif parsed_info["time_info"].get("duration_hours"):
            duration = int(parsed_info["time_info"]["duration_hours"])
            end_time = start_time + timedelta(hours=duration)
        else:
            # デフォルトで1時間
            end_time = start_time + timedelta(hours=1)

        print(f"\n予定情報:")
        print(f"開始時刻: {start_time}")
        print(f"終了時刻: {end_time}")

        # 詳細情報の構築
        location_info = parsed_info.get("location", {})
        location_str = ""
        if location_info.get("name"):
            location_str += f"場所: {location_info['name']}\n"
        if location_info.get("address"):
            location_str += f"住所: {location_info['address']}\n"
        if location_info.get("notes"):
            location_str += f"アクセス: {location_info['notes']}\n"

        description = ""
        if parsed_info.get("event_type"):
            description += f"イベント種別: {parsed_info['event_type']}\n"
        if location_str:
            description += f"\n{location_str}"
        if parsed_info.get("description"):
            description += f"\n{parsed_info['description']}"

        # カレンダーに予定を追加
        result = add_event(
            summary=parsed_info["title"],
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            description=description.strip()
        )

        return f"""
画像からの予定登録結果:
タイトル: {parsed_info['title']}
日付: {start_time.strftime('%Y-%m-%d')}
時間: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}
場所: {location_info.get('name', '(指定なし)')}
イベント種別: {parsed_info.get('event_type', '(指定なし)')}
詳細: {parsed_info.get('description', '(なし)')}
登録結果: {result}
"""

    except Exception as e:
        import traceback
        print(f"エラーの詳細:\n{traceback.format_exc()}")
        return f"エラーが発生しました: {str(e)}"

async def main():
    # テスト画像のパス
    image_path = "tests/images/kyogen.jpg"
    
    print(f"画像ファイル: {image_path}")
    result = await process_image_calendar_request(image_path)
    print(result)

if __name__ == "__main__":
    asyncio.run(main())