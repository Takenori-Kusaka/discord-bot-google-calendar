"""エージェントツール定義と実行"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ツール定義スキーマ
TOOL_DEFINITIONS = [
    {
        "name": "get_calendar_events",
        "description": "Googleカレンダーから予定を取得します。今日、明日、今週などの予定を確認できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_range": {
                    "type": "string",
                    "enum": ["today", "tomorrow", "this_week", "next_week"],
                    "description": "取得する期間",
                }
            },
            "required": ["date_range"],
        },
    },
    {
        "name": "get_weather",
        "description": "木津川市の天気予報を取得します。今日の天気や週間予報を確認できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "何日分の予報を取得するか（1-7）",
                    "default": 1,
                }
            },
        },
    },
    {
        "name": "search_events",
        "description": "木津川市・奈良市周辺の地域イベントを検索します。家族向けのイベントを探せます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "検索キーワード（例: 子供向け、週末、無料）",
                }
            },
        },
    },
    {
        "name": "get_life_info",
        "description": "家族に関連する法改正や制度変更などの生活影響情報を取得します。児童手当、保育、税金などの情報が確認できます。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_today_info",
        "description": "今日が何の日かを取得します。記念日や豆知識を提供します。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_family_info",
        "description": "家族情報（ゴミ出し日、よく行く場所など）を参照します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["garbage", "favorite_places", "all"],
                    "description": "取得する情報カテゴリ",
                }
            },
            "required": ["category"],
        },
    },
    {
        "name": "create_calendar_event",
        "description": "Googleカレンダーに新しい予定を登録します。日時、タイトル、場所などを指定できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "予定のタイトル",
                },
                "date": {
                    "type": "string",
                    "description": "予定の日付（YYYY-MM-DD形式、例: 2026-01-25）",
                },
                "start_time": {
                    "type": "string",
                    "description": "開始時刻（HH:MM形式、例: 14:30）。省略時は終日予定になります。",
                },
                "end_time": {
                    "type": "string",
                    "description": "終了時刻（HH:MM形式、例: 15:30）。省略時は開始から1時間後になります。",
                },
                "description": {
                    "type": "string",
                    "description": "予定の説明（任意）",
                },
                "location": {
                    "type": "string",
                    "description": "場所（任意）",
                },
            },
            "required": ["summary", "date"],
        },
    },
    {
        "name": "web_search",
        "description": "インターネットで情報を検索します。最新のニュース、店舗情報、営業時間、ルート検索、一般的な質問など、カレンダーや天気以外の情報を調べるときに使用します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "検索したい内容や質問（例: 「高の原イオンの営業時間」「最近のニュース」「子連れで行けるカフェ」）",
                },
                "search_type": {
                    "type": "string",
                    "enum": [
                        "general",
                        "business_hours",
                        "route",
                        "news",
                        "restaurant",
                    ],
                    "description": "検索の種類。general=一般検索、business_hours=営業時間検索、route=経路検索、news=ニュース検索、restaurant=飲食店検索",
                    "default": "general",
                },
                "location": {
                    "type": "string",
                    "description": "場所（経路検索や店舗検索時に使用）",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "set_reminder",
        "description": "指定した日時にリマインダーを設定します。一度きりの通知や、毎日・毎週の繰り返し通知も設定できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "リマインダーのメッセージ（例: 電話をする、薬を飲む）",
                },
                "date": {
                    "type": "string",
                    "description": "リマインダーの日付（YYYY-MM-DD形式）。繰り返しの場合は開始日。",
                },
                "time": {
                    "type": "string",
                    "description": "リマインダーの時刻（HH:MM形式、例: 10:00）",
                },
                "repeat": {
                    "type": "string",
                    "enum": ["none", "daily", "weekly", "monthly"],
                    "description": "繰り返し設定。none=一度のみ、daily=毎日、weekly=毎週、monthly=毎月",
                    "default": "none",
                },
                "repeat_day": {
                    "type": "string",
                    "enum": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                    "description": "毎週リマインダーの場合の曜日",
                },
            },
            "required": ["message", "date", "time"],
        },
    },
    {
        "name": "list_reminders",
        "description": "設定されているリマインダーの一覧を表示します。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "delete_reminder",
        "description": "指定したIDのリマインダーを削除します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {
                    "type": "string",
                    "description": "削除するリマインダーのID",
                },
            },
            "required": ["reminder_id"],
        },
    },
    {
        "name": "add_shopping_item",
        "description": "買い物リストにアイテムを追加します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "商品名（例: 牛乳、卵、食パン）",
                },
                "quantity": {
                    "type": "string",
                    "description": "数量（例: 2本、1パック）",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "食品",
                        "野菜・果物",
                        "肉・魚",
                        "乳製品",
                        "飲料",
                        "調味料",
                        "日用品",
                        "洗剤・衛生用品",
                        "ベビー用品",
                        "医薬品",
                        "その他",
                    ],
                    "description": "カテゴリ（省略時は自動判定）",
                },
                "note": {
                    "type": "string",
                    "description": "メモ（例: 特売品、〇〇用）",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_shopping",
        "description": "買い物リストを表示します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "カテゴリでフィルタ（省略時は全件）",
                },
            },
        },
    },
    {
        "name": "remove_shopping_item",
        "description": "買い物リストからアイテムを削除します。商品名またはIDで指定できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "item": {
                    "type": "string",
                    "description": "削除する商品名またはID",
                },
            },
            "required": ["item"],
        },
    },
    {
        "name": "search_route",
        "description": "電車・バスの経路や時刻を検索します。出発地から目的地までのルート、所要時間、乗り換え情報を取得できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "出発地（駅名や地名、例: 木津駅、高の原）",
                },
                "destination": {
                    "type": "string",
                    "description": "目的地（駅名や地名、例: 京都駅、奈良駅）",
                },
                "departure_time": {
                    "type": "string",
                    "description": "出発時刻（HH:MM形式、例: 09:00）。省略時は現在時刻",
                },
                "arrival_time": {
                    "type": "string",
                    "description": "到着希望時刻（HH:MM形式、例: 10:30）。指定時はこの時刻に着くルートを検索",
                },
                "date": {
                    "type": "string",
                    "description": "日付（YYYY-MM-DD形式または「明日」「今日」）。省略時は今日",
                },
                "search_type": {
                    "type": "string",
                    "enum": ["normal", "last_train", "first_train"],
                    "description": "検索種類: normal=通常検索、last_train=終電検索、first_train=始発検索",
                    "default": "normal",
                },
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "name": "suggest_recipe",
        "description": "材料や条件からレシピを提案します。冷蔵庫にある材料で作れるレシピや、特定の料理のレシピを検索できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "ingredients": {
                    "type": "string",
                    "description": "使いたい材料（カンマ区切り、例: 鶏肉, 玉ねぎ, じゃがいも）",
                },
                "dish_type": {
                    "type": "string",
                    "description": "料理の種類（例: 和食、洋食、中華、主菜、副菜、スープ）",
                },
                "servings": {
                    "type": "integer",
                    "description": "何人前か（デフォルト: 4人前）",
                    "default": 4,
                },
                "cooking_time": {
                    "type": "string",
                    "enum": ["quick", "normal", "long"],
                    "description": "調理時間: quick=15分以内、normal=30分程度、long=1時間以上",
                },
                "dietary_restrictions": {
                    "type": "string",
                    "description": "食事制限（例: ベジタリアン、アレルギー食材、低カロリー）",
                },
                "request": {
                    "type": "string",
                    "description": "具体的なリクエスト（例: 子供が喜ぶ料理、作り置きできるもの）",
                },
            },
        },
    },
    {
        "name": "search_nearby_store",
        "description": "木津川市・奈良市周辺で店舗を検索します。スーパー、ドラッグストア、ホームセンター、飲食店などを探せます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "store_type": {
                    "type": "string",
                    "description": "店舗の種類（例: スーパー、ドラッグストア、ホームセンター、カフェ、レストラン、病院、公園）",
                },
                "product": {
                    "type": "string",
                    "description": "探している商品やサービス（例: おむつ、子供服、文房具）",
                },
                "area": {
                    "type": "string",
                    "description": "エリア（例: 高の原、木津川台、精華町）。省略時は木津川市周辺",
                },
                "requirements": {
                    "type": "string",
                    "description": "追加の要件（例: 駐車場あり、子連れOK、24時間営業）",
                },
            },
        },
    },
    {
        "name": "track_package",
        "description": "荷物の配送状況を追跡します。ヤマト運輸、佐川急便、日本郵便などの追跡番号から配送状況を確認できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "tracking_number": {
                    "type": "string",
                    "description": "追跡番号（伝票番号）",
                },
                "carrier": {
                    "type": "string",
                    "enum": ["yamato", "sagawa", "japanpost", "auto"],
                    "description": "配送業者（yamato=ヤマト運輸、sagawa=佐川急便、japanpost=日本郵便、auto=自動判定）",
                    "default": "auto",
                },
            },
            "required": ["tracking_number"],
        },
    },
    {
        "name": "add_housework_task",
        "description": "定期的な家事タスクを登録します。エアコンフィルター掃除、換気扇掃除などのメンテナンスタスクを管理できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "タスク名（例: エアコンフィルター掃除、浴室カビ取り）",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "掃除",
                        "洗濯",
                        "料理",
                        "買い出し",
                        "ゴミ出し",
                        "整理整頓",
                        "住宅メンテナンス",
                        "家電メンテナンス",
                        "庭・外回り",
                        "その他",
                    ],
                    "description": "カテゴリ",
                },
                "interval_days": {
                    "type": "integer",
                    "description": "繰り返し間隔（日数）。0=繰り返しなし、7=毎週、30=毎月、90=3ヶ月毎",
                },
                "note": {
                    "type": "string",
                    "description": "メモ",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "done_housework",
        "description": "家事タスクを完了としてマークします。タスク名またはIDで指定できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "完了したタスク名またはID（例: エアコンフィルター掃除）",
                },
            },
            "required": ["task"],
        },
    },
    {
        "name": "list_housework",
        "description": "家事タスクの一覧を表示します。期限切れのタスクも確認できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "カテゴリでフィルタ（省略時は全件）",
                },
                "due_only": {
                    "type": "boolean",
                    "description": "trueの場合、期限切れのタスクのみ表示",
                    "default": False,
                },
            },
        },
    },
    {
        "name": "control_light",
        "description": "部屋の照明を制御します。ON/OFFを切り替えられます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "enum": ["書斎", "リビング", "寝室", "子供部屋", "廊下"],
                    "description": "部屋名",
                },
                "action": {
                    "type": "string",
                    "enum": ["on", "off"],
                    "description": "on=点灯、off=消灯",
                },
            },
            "required": ["room", "action"],
        },
    },
    {
        "name": "control_climate",
        "description": "部屋のエアコンを制御します。ON/OFF、温度設定、モード切替ができます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "enum": ["書斎", "リビング", "寝室", "子供部屋"],
                    "description": "部屋名",
                },
                "action": {
                    "type": "string",
                    "enum": ["on", "off"],
                    "description": "on=運転開始、off=停止",
                },
                "temperature": {
                    "type": "integer",
                    "description": "設定温度（16-30）",
                },
                "mode": {
                    "type": "string",
                    "enum": ["cool", "heat", "dry", "fan_only"],
                    "description": "運転モード（cool=冷房、heat=暖房、dry=除湿、fan_only=送風）",
                    "default": "cool",
                },
            },
            "required": ["room", "action"],
        },
    },
    {
        "name": "get_room_environment",
        "description": "部屋の温度・湿度などの環境情報を取得します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "enum": ["書斎", "リビング", "寝室", "子供部屋", "all"],
                    "description": "部屋名（all=全部屋）",
                },
            },
        },
    },
    {
        "name": "smart_home_speak",
        "description": "スマートスピーカーから音声でメッセージを伝えます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "伝えるメッセージ",
                },
                "room": {
                    "type": "string",
                    "enum": ["書斎", "リビング", "子供部屋"],
                    "description": "スピーカーがある部屋",
                    "default": "リビング",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "record_expense",
        "description": "支出を記録します。買い物や支払いの金額を家計簿に記録できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "integer",
                    "description": "金額（円）",
                },
                "description": {
                    "type": "string",
                    "description": "内容や購入場所（例: スーパーで食材、病院代）",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "食費",
                        "日用品",
                        "交通費",
                        "医療費",
                        "教育費",
                        "娯楽費",
                        "衣服費",
                        "通信費",
                        "水道光熱費",
                        "住居費",
                        "保険料",
                        "子供関連",
                        "その他",
                    ],
                    "description": "カテゴリ（省略時は自動判定）",
                },
                "date": {
                    "type": "string",
                    "description": "日付（YYYY-MM-DD形式、省略時は今日）",
                },
                "payment_method": {
                    "type": "string",
                    "enum": [
                        "現金",
                        "クレジットカード",
                        "デビットカード",
                        "電子マネー",
                        "QRコード決済",
                        "銀行振込",
                    ],
                    "description": "支払い方法",
                },
            },
            "required": ["amount"],
        },
    },
    {
        "name": "record_income",
        "description": "収入を記録します。給与や児童手当などの入金を記録できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "integer",
                    "description": "金額（円）",
                },
                "description": {
                    "type": "string",
                    "description": "内容（例: 給与、児童手当）",
                },
                "category": {
                    "type": "string",
                    "enum": ["給与", "副業", "児童手当", "その他収入"],
                    "description": "カテゴリ",
                    "default": "その他収入",
                },
                "date": {
                    "type": "string",
                    "description": "日付（YYYY-MM-DD形式、省略時は今日）",
                },
            },
            "required": ["amount"],
        },
    },
    {
        "name": "get_expense_summary",
        "description": "月ごとの家計簿サマリーを表示します。収支やカテゴリ別支出を確認できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "年（省略時は今年）",
                },
                "month": {
                    "type": "integer",
                    "description": "月（1-12、省略時は今月）",
                },
            },
        },
    },
    {
        "name": "list_expenses",
        "description": "最近の支出・収入記録を一覧表示します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "表示件数（デフォルト10件）",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "get_school_info",
        "description": "子供の学校・保育園情報を取得します。開園時間、連絡先などを確認できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "child": {
                    "type": "string",
                    "description": "子供の名称（お嬢様、坊ちゃま）",
                },
            },
        },
    },
    {
        "name": "get_school_events",
        "description": "学校・保育園の行事予定を取得します。運動会、お遊戯会などの予定を確認できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "何日先まで取得するか（デフォルト30日）",
                    "default": 30,
                },
            },
        },
    },
    {
        "name": "get_school_items",
        "description": "学校・保育園の持ち物リストを取得します。毎日・週ごと・特別な持ち物を確認できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_type": {
                    "type": "string",
                    "enum": ["daily", "weekly", "special"],
                    "description": "持ち物タイプ（daily=毎日、weekly=週ごと、special=特別）",
                    "default": "daily",
                },
            },
        },
    },
    # 健康記録ツール
    {
        "name": "record_symptom",
        "description": "家族の症状・体調不良を記録します。体温も記録できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "person": {
                    "type": "string",
                    "description": "対象者（旦那様、奥様、お嬢様など）",
                },
                "symptom": {
                    "type": "string",
                    "description": "症状（例: 発熱、咳、鼻水、腹痛）",
                },
                "temperature": {
                    "type": "number",
                    "description": "体温（省略可）",
                },
                "notes": {
                    "type": "string",
                    "description": "備考（省略可）",
                },
            },
            "required": ["person", "symptom"],
        },
    },
    {
        "name": "record_hospital_visit",
        "description": "通院記録を追加します。病院名、診断結果、処方薬などを記録できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "person": {
                    "type": "string",
                    "description": "対象者（旦那様、奥様、お嬢様など）",
                },
                "hospital": {
                    "type": "string",
                    "description": "病院名",
                },
                "reason": {
                    "type": "string",
                    "description": "受診理由",
                },
                "diagnosis": {
                    "type": "string",
                    "description": "診断結果（省略可）",
                },
                "prescription": {
                    "type": "string",
                    "description": "処方薬（省略可）",
                },
                "next_visit": {
                    "type": "string",
                    "description": "次回予約日（省略可）",
                },
            },
            "required": ["person", "hospital", "reason"],
        },
    },
    {
        "name": "get_health_info",
        "description": "家族の健康情報を取得します。アレルギー、持病、かかりつけ病院などを確認できます。",
        "input_schema": {
            "type": "object",
            "properties": {
                "person": {
                    "type": "string",
                    "description": "対象者（省略時は全員）",
                },
            },
        },
    },
    {
        "name": "get_health_records",
        "description": "健康記録（症状、通院、服薬など）を取得します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "person": {
                    "type": "string",
                    "description": "対象者（省略時は全員）",
                },
                "record_type": {
                    "type": "string",
                    "enum": ["symptom", "hospital", "medicine", "checkup"],
                    "description": "記録タイプ（省略時は全タイプ）",
                },
                "days": {
                    "type": "integer",
                    "description": "何日前までの記録を取得するか",
                    "default": 30,
                },
            },
        },
    },
]


@dataclass
class ToolResult:
    """ツール実行結果"""

    tool_use_id: str
    content: str
    is_error: bool = False


class ToolExecutor:
    """ツール実行器"""

    def __init__(
        self,
        calendar_client=None,
        weather_client=None,
        event_search_client=None,
        life_info_client=None,
        today_info_client=None,
        web_search_client=None,
        reminder_client=None,
        shopping_list_client=None,
        housework_client=None,
        home_assistant_client=None,
        expense_client=None,
        school_client=None,
        health_client=None,
        family_data: Optional[dict] = None,
        timezone: str = "Asia/Tokyo",
    ):
        """初期化

        Args:
            calendar_client: Google Calendarクライアント
            weather_client: 天気クライアント
            event_search_client: イベント検索クライアント
            life_info_client: 生活影響情報クライアント
            today_info_client: 今日は何の日クライアント
            web_search_client: Web検索クライアント
            reminder_client: リマインダークライアント
            shopping_list_client: 買い物リストクライアント
            housework_client: 家事記録クライアント
            home_assistant_client: Home Assistantクライアント
            expense_client: 家計簿クライアント
            school_client: 学校情報クライアント
            health_client: 健康記録クライアント
            family_data: 家族情報
            timezone: タイムゾーン
        """
        self.calendar_client = calendar_client
        self.weather_client = weather_client
        self.event_search_client = event_search_client
        self.life_info_client = life_info_client
        self.today_info_client = today_info_client
        self.web_search_client = web_search_client
        self.reminder_client = reminder_client
        self.shopping_list_client = shopping_list_client
        self.housework_client = housework_client
        self.home_assistant_client = home_assistant_client
        self.expense_client = expense_client
        self.school_client = school_client
        self.health_client = health_client
        self.family_data = family_data or {}
        self.timezone = timezone

        # ツールハンドラマッピング
        self._handlers: dict[str, Callable] = {
            "get_calendar_events": self._get_calendar_events,
            "get_weather": self._get_weather,
            "search_events": self._search_events,
            "get_life_info": self._get_life_info,
            "get_today_info": self._get_today_info,
            "get_family_info": self._get_family_info,
            "create_calendar_event": self._create_calendar_event,
            "web_search": self._web_search,
            "set_reminder": self._set_reminder,
            "list_reminders": self._list_reminders,
            "delete_reminder": self._delete_reminder,
            "add_shopping_item": self._add_shopping_item,
            "list_shopping": self._list_shopping,
            "remove_shopping_item": self._remove_shopping_item,
            "search_route": self._search_route,
            "suggest_recipe": self._suggest_recipe,
            "search_nearby_store": self._search_nearby_store,
            "track_package": self._track_package,
            "add_housework_task": self._add_housework_task,
            "done_housework": self._done_housework,
            "list_housework": self._list_housework,
            "control_light": self._control_light,
            "control_climate": self._control_climate,
            "get_room_environment": self._get_room_environment,
            "smart_home_speak": self._smart_home_speak,
            "record_expense": self._record_expense,
            "record_income": self._record_income,
            "get_expense_summary": self._get_expense_summary,
            "list_expenses": self._list_expenses,
            "get_school_info": self._get_school_info,
            "get_school_events": self._get_school_events,
            "get_school_items": self._get_school_items,
            # 健康記録
            "record_symptom": self._record_symptom,
            "record_hospital_visit": self._record_hospital_visit,
            "get_health_info": self._get_health_info,
            "get_health_records": self._get_health_records,
        }

        logger.info("Tool executor initialized")

    async def execute(
        self, tool_name: str, tool_input: dict, tool_use_id: str
    ) -> ToolResult:
        """ツールを実行

        Args:
            tool_name: ツール名
            tool_input: ツール入力
            tool_use_id: ツール使用ID

        Returns:
            ToolResult: 実行結果
        """
        logger.info(f"Executing tool: {tool_name}", input=tool_input)

        if tool_name not in self._handlers:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error: Unknown tool '{tool_name}'",
                is_error=True,
            )

        try:
            result = await self._handlers[tool_name](tool_input)
            logger.info(f"Tool {tool_name} completed", result_length=len(result))
            return ToolResult(tool_use_id=tool_use_id, content=result)
        except Exception as e:
            logger.error(f"Tool {tool_name} failed", error=str(e))
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error executing {tool_name}: {str(e)}",
                is_error=True,
            )

    async def _get_calendar_events(self, tool_input: dict) -> str:
        """カレンダー予定を取得"""
        if not self.calendar_client:
            return "カレンダークライアントが設定されていません。"

        date_range = tool_input.get("date_range", "today")
        now = datetime.now(ZoneInfo(self.timezone))

        if date_range == "today":
            events = await self.calendar_client.get_today_events()
        elif date_range == "tomorrow":
            events = await self.calendar_client.get_events_for_date(
                now + timedelta(days=1)
            )
        elif date_range == "this_week":
            events = await self.calendar_client.get_week_events()
        elif date_range == "next_week":
            # 来週の予定（簡易実装）
            events = await self.calendar_client.get_week_events()
        else:
            events = await self.calendar_client.get_today_events()

        if not events:
            return f"{date_range}の予定はございません。"

        lines = [f"【{date_range}の予定】"]
        for event in events:
            time_str = event.start.strftime("%H:%M") if not event.all_day else "終日"
            lines.append(f"- {time_str}: {event.summary}")

        return "\n".join(lines)

    async def _get_weather(self, tool_input: dict) -> str:
        """天気予報を取得"""
        if not self.weather_client:
            return "天気クライアントが設定されていません。"

        days = tool_input.get("days", 1)

        if days == 1:
            weather = await self.weather_client.get_today_weather()
            if not weather:
                return "天気情報を取得できませんでした。"
            return f"【本日の天気】\n{weather.format_for_notification()}"
        else:
            forecasts = await self.weather_client.get_weather_forecast(days=days)
            if not forecasts:
                return "天気予報を取得できませんでした。"

            lines = [f"【{days}日間の天気予報】"]
            for forecast in forecasts:
                date_str = forecast.date.strftime("%m/%d(%a)")
                lines.append(
                    f"- {date_str}: {forecast.weather_description} "
                    f"({forecast.temperature_min:.0f}°C〜{forecast.temperature_max:.0f}°C)"
                )

            return "\n".join(lines)

    async def _search_events(self, tool_input: dict) -> str:
        """地域イベントを検索"""
        if not self.event_search_client:
            return "イベント検索クライアントが設定されていません。"

        query = tool_input.get("query", "")

        # イベント検索を実行
        search_results = await self.event_search_client.search_events()

        if not search_results:
            return "イベント情報を取得できませんでした。"

        # クエリでフィルタリング（簡易実装）
        if query:
            filtered = [r for r in search_results if query in str(r)]
            if filtered:
                search_results = filtered

        lines = ["【地域イベント情報】"]
        for result in search_results[:5]:  # 最大5件
            lines.append(f"- {result.get('title', '不明')}")
            if result.get("date"):
                lines.append(f"  日時: {result.get('date')}")
            if result.get("location"):
                lines.append(f"  場所: {result.get('location')}")

        return "\n".join(lines)

    async def _get_life_info(self, tool_input: dict) -> str:
        """生活影響情報を取得"""
        if not self.life_info_client:
            return "生活影響情報クライアントが設定されていません。"

        info_list = await self.life_info_client.get_all_life_info()

        if not info_list:
            return "現在、特筆すべき生活影響情報はございません。"

        return self.life_info_client.format_for_weekly_notification(info_list[:5])

    async def _get_today_info(self, tool_input: dict) -> str:
        """今日は何の日を取得"""
        if not self.today_info_client:
            return "今日は何の日クライアントが設定されていません。"

        info = await self.today_info_client.get_today_info()

        if not info:
            return "今日は何の日情報を取得できませんでした。"

        return f"【今日は何の日】\n{info.format_for_notification()}"

    async def _get_family_info(self, tool_input: dict) -> str:
        """家族情報を取得"""
        category = tool_input.get("category", "all")

        if not self.family_data:
            return "家族情報が設定されていません。"

        if category == "garbage":
            garbage = self.family_data.get("garbage", {})
            if not garbage:
                return "ごみ出し情報は設定されていません。"

            lines = ["【ごみ出しスケジュール】"]
            for schedule in garbage.get("schedule", []):
                lines.append(
                    f"- {schedule.get('type', '')}: {schedule.get('days', schedule.get('frequency', ''))}"
                )
            return "\n".join(lines)

        elif category == "favorite_places":
            location = self.family_data.get("location", {})
            places = location.get("favorite_places", [])
            if not places:
                return "お気に入りの場所は設定されていません。"

            lines = ["【よく行く場所】"]
            for place in places:
                lines.append(f"- {place.get('name', '')}: {place.get('type', '')}")
            return "\n".join(lines)

        else:  # all
            lines = []

            # ごみ出し
            garbage = self.family_data.get("garbage", {})
            if garbage:
                lines.append("【ごみ出しスケジュール】")
                for schedule in garbage.get("schedule", []):
                    lines.append(
                        f"- {schedule.get('type', '')}: {schedule.get('days', schedule.get('frequency', ''))}"
                    )

            # お気に入りの場所
            location = self.family_data.get("location", {})
            places = location.get("favorite_places", [])
            if places:
                lines.append("\n【よく行く場所】")
                for place in places:
                    lines.append(f"- {place.get('name', '')}: {place.get('type', '')}")

            return "\n".join(lines) if lines else "家族情報が設定されていません。"

    async def _create_calendar_event(self, tool_input: dict) -> str:
        """カレンダー予定を作成"""
        if not self.calendar_client:
            return "カレンダークライアントが設定されていません。"

        summary = tool_input.get("summary")
        date_str = tool_input.get("date")
        start_time_str = tool_input.get("start_time")
        end_time_str = tool_input.get("end_time")
        description = tool_input.get("description")
        location = tool_input.get("location")

        if not summary:
            return "予定のタイトルを指定してください。"
        if not date_str:
            return "予定の日付を指定してください。"

        try:
            # 日付をパース
            date = datetime.strptime(date_str, "%Y-%m-%d")
            date = date.replace(tzinfo=ZoneInfo(self.timezone))

            # 終日予定かどうか
            all_day = start_time_str is None

            if all_day:
                start = date
                end = None
            else:
                # 開始時刻をパース
                start_time = datetime.strptime(start_time_str, "%H:%M").time()
                start = datetime.combine(date.date(), start_time)
                start = start.replace(tzinfo=ZoneInfo(self.timezone))

                # 終了時刻をパース（省略時はNone）
                if end_time_str:
                    end_time = datetime.strptime(end_time_str, "%H:%M").time()
                    end = datetime.combine(date.date(), end_time)
                    end = end.replace(tzinfo=ZoneInfo(self.timezone))
                else:
                    end = None

            # イベント作成
            event = await self.calendar_client.create_event(
                summary=summary,
                start=start,
                end=end,
                description=description,
                location=location,
                all_day=all_day,
            )

            # 成功メッセージ
            if all_day:
                time_info = f"{date_str}（終日）"
            else:
                time_info = f"{date_str} {start_time_str}"
                if end_time_str:
                    time_info += f"〜{end_time_str}"

            result = f"予定を登録しました。\n\n【登録内容】\n- タイトル: {summary}\n- 日時: {time_info}"
            if location:
                result += f"\n- 場所: {location}"
            if description:
                result += f"\n- 説明: {description}"

            return result

        except ValueError as e:
            return f"日時の形式が正しくありません: {str(e)}\n日付はYYYY-MM-DD形式、時刻はHH:MM形式で指定してください。"
        except Exception as e:
            logger.error("Failed to create calendar event", error=str(e))
            return f"予定の登録に失敗しました: {str(e)}"

    async def _web_search(self, tool_input: dict) -> str:
        """Web検索を実行"""
        if not self.web_search_client:
            return "Web検索クライアントが設定されていません。"

        query = tool_input.get("query", "")
        search_type = tool_input.get("search_type", "general")
        location = tool_input.get("location", "")

        if not query:
            return "検索クエリを指定してください。"

        try:
            if search_type == "business_hours":
                result = await self.web_search_client.get_business_hours(
                    query, location
                )
            elif search_type == "route":
                # queryを出発地、locationを目的地として解釈
                if location:
                    result = await self.web_search_client.get_route_info(
                        query, location
                    )
                else:
                    result = await self.web_search_client.search(query)
            elif search_type == "news":
                result = await self.web_search_client.get_news(query, location)
            elif search_type == "restaurant":
                result = await self.web_search_client.search_restaurant(
                    cuisine=query, location=location
                )
            else:
                result = await self.web_search_client.general_query(query)

            return f"【Web検索結果】\n{result}"

        except Exception as e:
            logger.error("Web search failed", error=str(e))
            return f"Web検索中にエラーが発生しました: {str(e)}"

    async def _set_reminder(self, tool_input: dict) -> str:
        """リマインダーを設定"""
        if not self.reminder_client:
            return "リマインダークライアントが設定されていません。"

        message = tool_input.get("message", "")
        date_str = tool_input.get("date", "")
        time_str = tool_input.get("time", "")
        repeat = tool_input.get("repeat", "none")
        repeat_day = tool_input.get("repeat_day")

        if not message:
            return "リマインダーのメッセージを指定してください。"
        if not date_str:
            return "日付を指定してください。"
        if not time_str:
            return "時刻を指定してください。"

        try:
            # 日時をパース
            date = datetime.strptime(date_str, "%Y-%m-%d")
            time = datetime.strptime(time_str, "%H:%M").time()
            trigger_time = datetime.combine(date.date(), time)
            trigger_time = trigger_time.replace(tzinfo=ZoneInfo(self.timezone))

            # 繰り返し設定を変換
            repeat_setting = None if repeat == "none" else repeat

            # リマインダーを追加
            reminder = await self.reminder_client.add_reminder(
                message=message,
                trigger_time=trigger_time,
                repeat=repeat_setting,
                repeat_day=repeat_day,
            )

            # 成功メッセージ
            result = f"リマインダーを設定しました。\n\n"
            result += f"【設定内容】\n"
            result += f"- ID: {reminder.id}\n"
            result += f"- メッセージ: {message}\n"

            if repeat_setting == "daily":
                result += f"- 時刻: 毎日 {time_str}"
            elif repeat_setting == "weekly":
                day_names = {
                    "mon": "月曜",
                    "tue": "火曜",
                    "wed": "水曜",
                    "thu": "木曜",
                    "fri": "金曜",
                    "sat": "土曜",
                    "sun": "日曜",
                }
                day_name = (
                    day_names.get(repeat_day, repeat_day) if repeat_day else "指定なし"
                )
                result += f"- 時刻: 毎週{day_name} {time_str}"
            elif repeat_setting == "monthly":
                result += f"- 時刻: 毎月{date.day}日 {time_str}"
            else:
                result += f"- 日時: {date_str} {time_str}"

            return result

        except ValueError as e:
            return f"日時の形式が正しくありません: {str(e)}\n日付はYYYY-MM-DD形式、時刻はHH:MM形式で指定してください。"
        except Exception as e:
            logger.error("Failed to set reminder", error=str(e))
            return f"リマインダーの設定に失敗しました: {str(e)}"

    async def _list_reminders(self, tool_input: dict) -> str:
        """リマインダー一覧を取得"""
        if not self.reminder_client:
            return "リマインダークライアントが設定されていません。"

        return self.reminder_client.format_all_reminders()

    async def _delete_reminder(self, tool_input: dict) -> str:
        """リマインダーを削除"""
        if not self.reminder_client:
            return "リマインダークライアントが設定されていません。"

        reminder_id = tool_input.get("reminder_id", "")
        if not reminder_id:
            return "リマインダーIDを指定してください。"

        # 削除前に存在確認
        reminder = self.reminder_client.get_reminder(reminder_id)
        if not reminder:
            return f"ID '{reminder_id}' のリマインダーは見つかりませんでした。"

        success = await self.reminder_client.delete_reminder(reminder_id)
        if success:
            return f"リマインダー「{reminder.message}」を削除しました。"
        else:
            return f"リマインダーの削除に失敗しました。"

    async def _add_shopping_item(self, tool_input: dict) -> str:
        """買い物リストにアイテムを追加"""
        if not self.shopping_list_client:
            return "買い物リストクライアントが設定されていません。"

        name = tool_input.get("name", "")
        quantity = tool_input.get("quantity", "")
        category = tool_input.get("category")
        note = tool_input.get("note", "")

        if not name:
            return "商品名を指定してください。"

        try:
            item = self.shopping_list_client.add_item(
                name=name,
                quantity=quantity,
                category=category,
                note=note,
            )

            result = f"買い物リストに追加しました。\n\n"
            result += f"【追加内容】\n"
            result += f"- 商品名: {item.name}\n"
            if item.quantity:
                result += f"- 数量: {item.quantity}\n"
            result += f"- カテゴリ: {item.category}\n"
            result += f"- ID: {item.id}"

            return result

        except Exception as e:
            logger.error("Failed to add shopping item", error=str(e))
            return f"買い物リストへの追加に失敗しました: {str(e)}"

    async def _list_shopping(self, tool_input: dict) -> str:
        """買い物リストを表示"""
        if not self.shopping_list_client:
            return "買い物リストクライアントが設定されていません。"

        category = tool_input.get("category")
        return self.shopping_list_client.format_list(category)

    async def _remove_shopping_item(self, tool_input: dict) -> str:
        """買い物リストからアイテムを削除"""
        if not self.shopping_list_client:
            return "買い物リストクライアントが設定されていません。"

        item_str = tool_input.get("item", "")
        if not item_str:
            return "削除する商品名またはIDを指定してください。"

        # まずIDとして試す
        item = self.shopping_list_client.get_item(item_str)
        if item:
            self.shopping_list_client.remove_item(item_str)
            return f"「{item.name}」を買い物リストから削除しました。"

        # 商品名として試す
        removed_item = self.shopping_list_client.remove_item_by_name(item_str)
        if removed_item:
            return f"「{removed_item.name}」を買い物リストから削除しました。"

        return f"「{item_str}」は買い物リストに見つかりませんでした。"

    async def _search_route(self, tool_input: dict) -> str:
        """交通経路を検索"""
        if not self.web_search_client:
            return "交通情報検索にはWeb検索クライアントが必要です。"

        origin = tool_input.get("origin", "")
        destination = tool_input.get("destination", "")
        departure_time = tool_input.get("departure_time", "")
        arrival_time = tool_input.get("arrival_time", "")
        date = tool_input.get("date", "今日")
        search_type = tool_input.get("search_type", "normal")

        if not origin:
            return "出発地を指定してください。"
        if not destination:
            return "目的地を指定してください。"

        try:
            # 検索クエリを構築
            if search_type == "last_train":
                query = f"{origin}から{destination}までの終電を教えてください。最終の電車・バスの時刻と乗り換え情報を含めてください。"
            elif search_type == "first_train":
                query = f"{origin}から{destination}までの始発を教えてください。最初の電車・バスの時刻と乗り換え情報を含めてください。"
            elif arrival_time:
                query = f"{date}に{arrival_time}までに{destination}に着きたいです。{origin}からの電車・バスの経路と出発時刻を教えてください。乗り換え情報と所要時間も含めてください。"
            elif departure_time:
                query = f"{date}の{departure_time}頃に{origin}を出発して{destination}に行きたいです。電車・バスの経路を教えてください。乗り換え情報と所要時間も含めてください。"
            else:
                query = f"{origin}から{destination}までの電車・バスの経路を教えてください。現在時刻からのルート、所要時間、乗り換え情報を含めてください。"

            # Perplexity APIで検索
            result = await self.web_search_client.search(query)

            return f"【交通情報検索結果】\n{origin} → {destination}\n\n{result}"

        except Exception as e:
            logger.error("Route search failed", error=str(e))
            return f"交通情報の検索に失敗しました: {str(e)}"

    async def _suggest_recipe(self, tool_input: dict) -> str:
        """レシピを提案"""
        if not self.web_search_client:
            return "レシピ検索にはWeb検索クライアントが必要です。"

        ingredients = tool_input.get("ingredients", "")
        dish_type = tool_input.get("dish_type", "")
        servings = tool_input.get("servings", 4)
        cooking_time = tool_input.get("cooking_time", "")
        dietary_restrictions = tool_input.get("dietary_restrictions", "")
        request = tool_input.get("request", "")

        try:
            # 検索クエリを構築
            query_parts = []

            if ingredients:
                query_parts.append(f"以下の材料を使ったレシピを教えてください: {ingredients}")
            else:
                query_parts.append("おすすめのレシピを教えてください")

            if dish_type:
                query_parts.append(f"料理の種類: {dish_type}")

            if servings:
                query_parts.append(f"{servings}人前で作れるレシピ")

            if cooking_time:
                time_desc = {
                    "quick": "15分以内で作れる時短レシピ",
                    "normal": "30分程度で作れるレシピ",
                    "long": "じっくり時間をかけて作るレシピ",
                }
                query_parts.append(time_desc.get(cooking_time, ""))

            if dietary_restrictions:
                query_parts.append(f"食事制限: {dietary_restrictions}")

            if request:
                query_parts.append(f"リクエスト: {request}")

            query_parts.append(
                "レシピには以下を含めてください: 材料リスト（分量付き）、作り方の手順、調理時間の目安、コツやポイント"
            )

            query = "。".join(query_parts)

            # Perplexity APIで検索
            result = await self.web_search_client.search(query)

            # 結果をフォーマット
            header = "【レシピ提案】\n"
            if ingredients:
                header += f"材料: {ingredients}\n"
            if dish_type:
                header += f"種類: {dish_type}\n"
            if servings:
                header += f"人数: {servings}人前\n"
            header += "\n"

            return f"{header}{result}"

        except Exception as e:
            logger.error("Recipe suggestion failed", error=str(e))
            return f"レシピの検索に失敗しました: {str(e)}"

    async def _search_nearby_store(self, tool_input: dict) -> str:
        """近隣店舗を検索"""
        if not self.web_search_client:
            return "店舗検索にはWeb検索クライアントが必要です。"

        store_type = tool_input.get("store_type", "")
        product = tool_input.get("product", "")
        area = tool_input.get("area", "木津川市")
        requirements = tool_input.get("requirements", "")

        try:
            # 検索クエリを構築
            query_parts = []

            if store_type:
                query_parts.append(f"{area}周辺の{store_type}")
            elif product:
                query_parts.append(f"{area}周辺で{product}を買える店")
            else:
                query_parts.append(f"{area}周辺のおすすめの店舗")

            if product and store_type:
                query_parts.append(f"{product}を扱っている店")

            if requirements:
                query_parts.append(f"条件: {requirements}")

            query_parts.append(
                "店舗名、住所、営業時間、特徴を含めて教えてください。できれば複数の候補を挙げてください。"
            )

            query = "。".join(query_parts)

            # Perplexity APIで検索
            result = await self.web_search_client.search(query)

            # 結果をフォーマット
            header = "【店舗検索結果】\n"
            header += f"エリア: {area}\n"
            if store_type:
                header += f"店舗タイプ: {store_type}\n"
            if product:
                header += f"探している商品: {product}\n"
            header += "\n"

            return f"{header}{result}"

        except Exception as e:
            logger.error("Nearby store search failed", error=str(e))
            return f"店舗の検索に失敗しました: {str(e)}"

    async def _track_package(self, tool_input: dict) -> str:
        """荷物を追跡"""
        if not self.web_search_client:
            return "荷物追跡にはWeb検索クライアントが必要です。"

        tracking_number = tool_input.get("tracking_number", "")
        carrier = tool_input.get("carrier", "auto")

        if not tracking_number:
            return "追跡番号を指定してください。"

        try:
            # 配送業者を判定
            carrier_name = ""
            tracking_url = ""

            if carrier == "auto":
                # 追跡番号から業者を推測
                num = tracking_number.replace("-", "").replace(" ", "")
                if len(num) == 12 and num.isdigit():
                    carrier = "yamato"
                elif len(num) == 12 and num.startswith("0"):
                    carrier = "sagawa"
                elif len(num) in [11, 13] and num.isdigit():
                    carrier = "japanpost"

            if carrier == "yamato":
                carrier_name = "ヤマト運輸"
                tracking_url = f"https://toi.kuronekoyamato.co.jp/cgi-bin/tneko?number01={tracking_number}"
            elif carrier == "sagawa":
                carrier_name = "佐川急便"
                tracking_url = f"https://k2k.sagawa-exp.co.jp/p/web/okurijosearch.do?okurijoNo={tracking_number}"
            elif carrier == "japanpost":
                carrier_name = "日本郵便"
                tracking_url = f"https://trackings.post.japanpost.jp/services/srv/search?requestNo1={tracking_number}"
            else:
                carrier_name = "不明"

            # Perplexity APIで検索
            query = f"荷物追跡番号 {tracking_number}"
            if carrier_name != "不明":
                query = f"{carrier_name} 追跡番号 {tracking_number} の配送状況を教えてください。"
            else:
                query = f"追跡番号 {tracking_number} の荷物の配送状況を教えてください。配送業者も特定してください。"

            result = await self.web_search_client.search(query)

            # 結果をフォーマット
            header = "【荷物追跡結果】\n"
            header += f"追跡番号: {tracking_number}\n"
            if carrier_name != "不明":
                header += f"配送業者: {carrier_name}\n"
            if tracking_url:
                header += f"追跡ページ: {tracking_url}\n"
            header += "\n"

            return f"{header}{result}"

        except Exception as e:
            logger.error("Package tracking failed", error=str(e))
            return f"荷物追跡に失敗しました: {str(e)}"

    async def _add_housework_task(self, tool_input: dict) -> str:
        """家事タスクを追加"""
        if not self.housework_client:
            return "家事記録クライアントが設定されていません。"

        name = tool_input.get("name", "")
        category = tool_input.get("category", "その他")
        interval_days = tool_input.get("interval_days", 0)
        note = tool_input.get("note", "")

        if not name:
            return "タスク名を指定してください。"

        try:
            task = self.housework_client.add_task(
                name=name,
                category=category,
                interval_days=interval_days,
                note=note,
            )

            result = f"家事タスクを追加しました。\n\n"
            result += f"【登録内容】\n"
            result += f"- タスク名: {task.name}\n"
            result += f"- カテゴリ: {task.category}\n"
            if task.interval_days > 0:
                result += f"- 繰り返し: {task.interval_days}日毎\n"
            result += f"- ID: {task.id}"

            return result

        except Exception as e:
            logger.error("Failed to add housework task", error=str(e))
            return f"家事タスクの追加に失敗しました: {str(e)}"

    async def _done_housework(self, tool_input: dict) -> str:
        """家事タスクを完了としてマーク"""
        if not self.housework_client:
            return "家事記録クライアントが設定されていません。"

        task_str = tool_input.get("task", "")
        if not task_str:
            return "タスク名またはIDを指定してください。"

        # まずIDとして試す
        task = self.housework_client.get_task(task_str)
        if task:
            updated = self.housework_client.mark_done(task_str)
            if updated:
                result = f"「{updated.name}」を完了としてマークしました。\n"
                if updated.next_due:
                    from datetime import datetime

                    next_date = datetime.fromisoformat(updated.next_due)
                    result += f"次回予定日: {next_date.strftime('%Y年%m月%d日')}"
                return result

        # タスク名として試す
        updated = self.housework_client.mark_done_by_name(task_str)
        if updated:
            result = f"「{updated.name}」を完了としてマークしました。\n"
            if updated.next_due:
                from datetime import datetime

                next_date = datetime.fromisoformat(updated.next_due)
                result += f"次回予定日: {next_date.strftime('%Y年%m月%d日')}"
            return result

        return f"「{task_str}」というタスクは見つかりませんでした。"

    async def _list_housework(self, tool_input: dict) -> str:
        """家事タスク一覧を表示"""
        if not self.housework_client:
            return "家事記録クライアントが設定されていません。"

        category = tool_input.get("category")
        due_only = tool_input.get("due_only", False)

        return self.housework_client.format_list(category, due_only)

    async def _control_light(self, tool_input: dict) -> str:
        """照明を制御"""
        if not self.home_assistant_client:
            return "Home Assistantクライアントが設定されていません。"

        room = tool_input.get("room", "")
        action = tool_input.get("action", "")

        if not room:
            return "部屋を指定してください。"
        if not action:
            return "操作（on/off）を指定してください。"

        try:
            if action == "on":
                success = await self.home_assistant_client.light_on(room)
                if success:
                    return f"{room}の照明を点灯しました。"
                else:
                    return f"{room}の照明の点灯に失敗しました。"
            else:
                success = await self.home_assistant_client.light_off(room)
                if success:
                    return f"{room}の照明を消灯しました。"
                else:
                    return f"{room}の照明の消灯に失敗しました。"

        except Exception as e:
            logger.error("Light control failed", error=str(e))
            return f"照明の制御に失敗しました: {str(e)}"

    async def _control_climate(self, tool_input: dict) -> str:
        """エアコンを制御"""
        if not self.home_assistant_client:
            return "Home Assistantクライアントが設定されていません。"

        room = tool_input.get("room", "")
        action = tool_input.get("action", "")
        temperature = tool_input.get("temperature")
        mode = tool_input.get("mode", "cool")

        if not room:
            return "部屋を指定してください。"
        if not action:
            return "操作（on/off）を指定してください。"

        try:
            if action == "on":
                success = await self.home_assistant_client.climate_on(
                    room, temperature, mode
                )
                if success:
                    mode_names = {
                        "cool": "冷房",
                        "heat": "暖房",
                        "dry": "除湿",
                        "fan_only": "送風",
                    }
                    mode_name = mode_names.get(mode, mode)
                    result = f"{room}のエアコンを{mode_name}で運転開始しました。"
                    if temperature:
                        result += f" 設定温度: {temperature}°C"
                    return result
                else:
                    return f"{room}のエアコンの運転開始に失敗しました。"
            else:
                success = await self.home_assistant_client.climate_off(room)
                if success:
                    return f"{room}のエアコンを停止しました。"
                else:
                    return f"{room}のエアコンの停止に失敗しました。"

        except Exception as e:
            logger.error("Climate control failed", error=str(e))
            return f"エアコンの制御に失敗しました: {str(e)}"

    async def _get_room_environment(self, tool_input: dict) -> str:
        """部屋の環境情報を取得"""
        if not self.home_assistant_client:
            return "Home Assistantクライアントが設定されていません。"

        room = tool_input.get("room", "all")

        try:
            if room == "all":
                readings = await self.home_assistant_client.get_all_sensors()
                return self.home_assistant_client.format_sensor_readings(readings)
            else:
                reading = await self.home_assistant_client.get_room_sensors(room)
                if reading:
                    lines = [f"【{room}の環境】"]
                    if reading.temperature is not None:
                        lines.append(f"- 温度: {reading.temperature:.1f}°C")
                    if reading.humidity is not None:
                        lines.append(f"- 湿度: {reading.humidity:.0f}%")
                    if len(lines) == 1:
                        lines.append("センサー情報を取得できませんでした。")
                    return "\n".join(lines)
                else:
                    return f"{room}のセンサー情報を取得できませんでした。"

        except Exception as e:
            logger.error("Get room environment failed", error=str(e))
            return f"環境情報の取得に失敗しました: {str(e)}"

    async def _smart_home_speak(self, tool_input: dict) -> str:
        """スマートスピーカーから音声を出力"""
        if not self.home_assistant_client:
            return "Home Assistantクライアントが設定されていません。"

        message = tool_input.get("message", "")
        room = tool_input.get("room", "リビング")

        if not message:
            return "メッセージを指定してください。"

        try:
            success = await self.home_assistant_client.speak(message, room)
            if success:
                return f"{room}のスピーカーからメッセージを伝えました。"
            else:
                return f"スピーカーへのメッセージ送信に失敗しました。"

        except Exception as e:
            logger.error("Smart home speak failed", error=str(e))
            return f"音声出力に失敗しました: {str(e)}"

    async def _record_expense(self, tool_input: dict) -> str:
        """支出を記録"""
        if not self.expense_client:
            return "家計簿クライアントが設定されていません。"

        amount = tool_input.get("amount")
        description = tool_input.get("description", "")
        category = tool_input.get("category")
        date = tool_input.get("date")
        payment_method = tool_input.get("payment_method", "")

        if not amount:
            return "金額を指定してください。"

        try:
            record = self.expense_client.add_expense(
                amount=amount,
                description=description,
                category=category,
                date=date,
                payment_method=payment_method,
            )

            result = f"支出を記録しました。\n\n"
            result += f"【記録内容】\n"
            result += f"- 金額: ¥{record.amount:,}\n"
            result += f"- カテゴリ: {record.category}\n"
            if record.description:
                result += f"- 内容: {record.description}\n"
            result += f"- 日付: {record.date}\n"
            if record.payment_method:
                result += f"- 支払方法: {record.payment_method}\n"
            result += f"- ID: {record.id}"

            return result

        except Exception as e:
            logger.error("Failed to record expense", error=str(e))
            return f"支出の記録に失敗しました: {str(e)}"

    async def _record_income(self, tool_input: dict) -> str:
        """収入を記録"""
        if not self.expense_client:
            return "家計簿クライアントが設定されていません。"

        amount = tool_input.get("amount")
        description = tool_input.get("description", "")
        category = tool_input.get("category", "その他収入")
        date = tool_input.get("date")

        if not amount:
            return "金額を指定してください。"

        try:
            record = self.expense_client.add_income(
                amount=amount,
                description=description,
                category=category,
                date=date,
            )

            result = f"収入を記録しました。\n\n"
            result += f"【記録内容】\n"
            result += f"- 金額: ¥{record.amount:,}\n"
            result += f"- カテゴリ: {record.category}\n"
            if record.description:
                result += f"- 内容: {record.description}\n"
            result += f"- 日付: {record.date}\n"
            result += f"- ID: {record.id}"

            return result

        except Exception as e:
            logger.error("Failed to record income", error=str(e))
            return f"収入の記録に失敗しました: {str(e)}"

    async def _get_expense_summary(self, tool_input: dict) -> str:
        """家計簿サマリーを取得"""
        if not self.expense_client:
            return "家計簿クライアントが設定されていません。"

        year = tool_input.get("year")
        month = tool_input.get("month")

        try:
            return self.expense_client.format_summary(year, month)
        except Exception as e:
            logger.error("Failed to get expense summary", error=str(e))
            return f"サマリーの取得に失敗しました: {str(e)}"

    async def _list_expenses(self, tool_input: dict) -> str:
        """最近の支出・収入を一覧表示"""
        if not self.expense_client:
            return "家計簿クライアントが設定されていません。"

        limit = tool_input.get("limit", 10)

        try:
            return self.expense_client.format_recent_records(limit)
        except Exception as e:
            logger.error("Failed to list expenses", error=str(e))
            return f"記録の取得に失敗しました: {str(e)}"

    async def _get_school_info(self, tool_input: dict) -> str:
        """学校情報を取得"""
        if not self.school_client:
            return "学校情報クライアントが設定されていません。"

        child = tool_input.get("child", "")

        try:
            if child:
                school = self.school_client.get_school_by_child(child)
                if school:
                    return self.school_client.format_school_info(school)
                else:
                    return f"{child}の学校情報は登録されていません。"
            else:
                schools = self.school_client.list_schools()
                if not schools:
                    return "学校情報は登録されていません。"

                lines = []
                for school in schools:
                    lines.append(self.school_client.format_school_info(school))
                return "\n\n".join(lines)

        except Exception as e:
            logger.error("Failed to get school info", error=str(e))
            return f"学校情報の取得に失敗しました: {str(e)}"

    async def _get_school_events(self, tool_input: dict) -> str:
        """学校行事を取得"""
        if not self.school_client:
            return "学校情報クライアントが設定されていません。"

        days = tool_input.get("days", 30)

        try:
            return self.school_client.format_upcoming_events(days)
        except Exception as e:
            logger.error("Failed to get school events", error=str(e))
            return f"行事予定の取得に失敗しました: {str(e)}"

    async def _get_school_items(self, tool_input: dict) -> str:
        """持ち物リストを取得"""
        if not self.school_client:
            return "学校情報クライアントが設定されていません。"

        item_type = tool_input.get("item_type", "daily")

        try:
            return self.school_client.format_required_items(item_type)
        except Exception as e:
            logger.error("Failed to get school items", error=str(e))
            return f"持ち物リストの取得に失敗しました: {str(e)}"

    # ========================================
    # 健康記録ツール
    # ========================================

    async def _record_symptom(self, tool_input: dict) -> str:
        """症状を記録"""
        if not self.health_client:
            return "健康記録クライアントが設定されていません。"

        person = tool_input.get("person", "")
        symptom = tool_input.get("symptom", "")
        temperature = tool_input.get("temperature")
        notes = tool_input.get("notes", "")

        if not person or not symptom:
            return "対象者と症状を指定してください。"

        try:
            record = self.health_client.add_symptom(
                person=person,
                symptom=symptom,
                temperature=temperature,
                notes=notes,
            )

            result = f"{person}の症状を記録しました。\n"
            result += f"日付: {record.date}\n"
            result += f"症状: {symptom}"
            if temperature:
                result += f"\n体温: {temperature}℃"
            if notes:
                result += f"\n備考: {notes}"

            return result

        except Exception as e:
            logger.error("Failed to record symptom", error=str(e))
            return f"症状の記録に失敗しました: {str(e)}"

    async def _record_hospital_visit(self, tool_input: dict) -> str:
        """通院記録を追加"""
        if not self.health_client:
            return "健康記録クライアントが設定されていません。"

        person = tool_input.get("person", "")
        hospital = tool_input.get("hospital", "")
        reason = tool_input.get("reason", "")
        diagnosis = tool_input.get("diagnosis", "")
        prescription = tool_input.get("prescription", "")
        next_visit = tool_input.get("next_visit", "")

        if not person or not hospital or not reason:
            return "対象者、病院名、受診理由を指定してください。"

        try:
            record = self.health_client.add_hospital_visit(
                person=person,
                hospital=hospital,
                reason=reason,
                diagnosis=diagnosis,
                prescription=prescription,
                next_visit=next_visit,
            )

            result = f"{person}の通院記録を追加しました。\n"
            result += f"日付: {record.date}\n"
            result += f"病院: {hospital}\n"
            result += f"理由: {reason}"
            if diagnosis:
                result += f"\n診断: {diagnosis}"
            if prescription:
                result += f"\n処方: {prescription}"
            if next_visit:
                result += f"\n次回予約: {next_visit}"

            return result

        except Exception as e:
            logger.error("Failed to record hospital visit", error=str(e))
            return f"通院記録の追加に失敗しました: {str(e)}"

    async def _get_health_info(self, tool_input: dict) -> str:
        """健康情報を取得"""
        if not self.health_client:
            return "健康記録クライアントが設定されていません。"

        person = tool_input.get("person")

        try:
            if person:
                member = self.health_client.get_member_info(person)
                if member:
                    return self.health_client.format_member_info(member)
                else:
                    return f"{person}の健康情報は登録されていません。"
            else:
                # 全員の情報
                lines = []
                for name, member in self.health_client.family_members.items():
                    lines.append(self.health_client.format_member_info(member))
                    lines.append("")

                if not lines:
                    return "家族の健康情報が登録されていません。"
                return "\n".join(lines).strip()

        except Exception as e:
            logger.error("Failed to get health info", error=str(e))
            return f"健康情報の取得に失敗しました: {str(e)}"

    async def _get_health_records(self, tool_input: dict) -> str:
        """健康記録を取得"""
        if not self.health_client:
            return "健康記録クライアントが設定されていません。"

        person = tool_input.get("person")
        record_type = tool_input.get("record_type")
        days = tool_input.get("days", 30)

        try:
            return self.health_client.format_recent_records(
                person=person,
                record_type=record_type,
                days=days,
            )
        except Exception as e:
            logger.error("Failed to get health records", error=str(e))
            return f"健康記録の取得に失敗しました: {str(e)}"


def get_tool_definitions() -> list[dict]:
    """ツール定義を取得"""
    return TOOL_DEFINITIONS
