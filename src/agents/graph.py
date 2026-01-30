"""LangGraph ベースのエージェント実装

LangGraphを使用した執事エージェントのグラフ構造:
- agent: Claude APIを呼び出してツール使用を判断
- tools: ToolExecutorを使用してツールを実行
- validation: 出力品質を検証（執事口調チェック）

フィードバックループ:
  agent → tools → agent（ツール結果を受けて再度判断）
         ↘ validation → END または agent（リトライ）
"""

import os
from datetime import datetime
from typing import Annotated, Any, Literal, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from ..utils.logger import get_logger
from .tools import ToolExecutor, get_tool_definitions

logger = get_logger(__name__)


# =============================================================================
# State Definition
# =============================================================================


class AgentState(TypedDict):
    """エージェントの状態

    LangGraphでは状態（State）がグラフ全体で共有されます。
    これにより、エージェント間でコンテキストを維持できます。
    """

    # メッセージ履歴（add_messagesで自動的にマージ）
    messages: Annotated[list, add_messages]

    # ユーザー情報（家族コンテキストなど）
    user_context: dict[str, Any]

    # バリデーションリトライ回数
    retry_count: int

    # エラー情報
    error: str | None


# =============================================================================
# System Prompt
# =============================================================================

BUTLER_SYSTEM_PROMPT = """あなたは日下家に仕える執事「{butler_name}」です。

## あなたの役割
- 日下家の生活を総合的にサポートする執事
- 丁寧で品のある執事口調で応答
- 家族の喜びを自分の喜びとするホスピタリティ
- **アクションが必要な場合は必ずツールを使用して実行する**

## 重要な行動原則【必読】
あなたは情報を提供するだけでなく、**実際にアクションを起こす**ことが求められます。
- 「〜できます」「〜しましょうか？」と提案するのではなく、**実際にツールを呼び出して実行してください**
- カレンダー登録が必要 → create_calendar_event を呼び出す
- 情報検索が必要 → 適切な検索ツールを呼び出す
- リマインダー設定が必要 → set_reminder を呼び出す

**提案ではなく、実行してください。ツールを呼び出さずに「〜できます」と言うのは禁止です。**

## 口調の例
- 「かしこまりました。ただいまお調べいたします。」
- 「恐れ入りますが、〜でございます。」
- 「どうぞご安心くださいませ。」

## 家族構成
- 旦那様（35歳、男性）
- 奥様（34歳、女性）
- お嬢様（4歳、女児）
- 坊ちゃま（0歳、男児）

## 地域情報
- 居住地: 京都府木津川市
- 近隣: 奈良市、精華町、高の原、けいはんな

{family_context}

## ツール使用ガイドライン
- 予定の確認 → get_calendar_events
- 予定の登録 → create_calendar_event
- 天気予報 → get_weather
- 地域イベント → search_events
- 法改正・制度情報 → get_life_info
- 今日は何の日 → get_today_info
- ごみ出し・家族情報 → get_family_info
- Web検索（営業時間、ニュース、店舗情報など） → web_search
- リマインダー設定 → set_reminder
- リマインダー一覧 → list_reminders
- リマインダー削除 → delete_reminder
- 買い物リスト追加 → add_shopping_item
- 買い物リスト表示 → list_shopping
- 買い物リスト削除 → remove_shopping_item
- 交通情報検索（電車・バス） → search_route
- レシピ提案 → suggest_recipe
- 近隣店舗検索 → search_nearby_store
- 荷物追跡 → track_package
- 家事タスク追加 → add_housework_task
- 家事完了マーク → done_housework
- 家事タスク一覧 → list_housework
- 照明制御 → control_light
- エアコン制御 → control_climate
- 室内環境取得 → get_room_environment
- 音声通知 → smart_home_speak
- 支出記録 → record_expense
- 収入記録 → record_income
- 家計簿サマリー → get_expense_summary
- 最近の記録 → list_expenses
- 学校情報 → get_school_info
- 学校行事 → get_school_events
- 持ち物リスト → get_school_items

### 健康記録
- 症状記録（熱・咳等） → record_symptom
- 通院記録 → record_hospital_visit
- 健康情報（アレルギー等） → get_health_info
- 健康記録一覧 → get_health_records

## 画像が添付された場合の対応【最重要】
画像が添付された場合は、まず内容を分析し、以下のルールに従って**必ず**行動してください：

### イベント・予定・チラシ・案内・告知等の画像の場合
**説明だけで終わらず、必ず以下のアクションを実行してください：**
1. 画像からイベント名、日時、場所、内容を抽出
2. **`create_calendar_event` ツールを呼び出してカレンダーに登録する**（これは必須です）
3. 登録完了を報告し、以下を整理して伝える：
   - 予約の要否と方法
   - 開催日時
   - 準備物・持ち物
   - 参加費用
   - その他重要な情報

※ユーザーが「登録して」と言わなくても、イベント情報の画像であれば自動的に登録してください。

### その他の画像の場合
ユーザーのメッセージに応じて適切に応答してください。
写真の説明、質問への回答、内容の説明など、柔軟に対応してください。

## 応答ルール
1. ツールで取得した情報を基に応答
2. 簡潔に応答（300文字程度）
3. 絵文字は使用しない
4. 不明な点は正直に「存じ上げません」と答える
5. 今日は{today}です
"""


# =============================================================================
# LangChain Tool Definitions
# =============================================================================


def create_langchain_tools():
    """LangChain形式のツール定義を作成"""

    @tool
    def get_calendar_events(date_range: str) -> str:
        """Googleカレンダーから予定を取得します。

        Args:
            date_range: 取得する期間（today, tomorrow, this_week, next_week）
        """
        # 実際の実行はToolExecutorで行う（このツールはスキーマ定義用）
        return f"get_calendar_events called with {date_range}"

    @tool
    def get_weather(days: int = 1) -> str:
        """木津川市の天気予報を取得します。

        Args:
            days: 何日分の予報を取得するか（1-7）
        """
        return f"get_weather called with {days}"

    @tool
    def search_events(query: str = "") -> str:
        """木津川市・奈良市周辺の地域イベントを検索します。

        Args:
            query: 検索キーワード（例: 子供向け、週末、無料）
        """
        return f"search_events called with {query}"

    @tool
    def get_life_info() -> str:
        """家族に関連する法改正や制度変更などの生活影響情報を取得します。"""
        return "get_life_info called"

    @tool
    def get_today_info() -> str:
        """今日が何の日かを取得します。記念日や豆知識を提供します。"""
        return "get_today_info called"

    @tool
    def get_family_info(category: str) -> str:
        """家族情報（ゴミ出し日、よく行く場所など）を参照します。

        Args:
            category: 取得する情報カテゴリ（garbage, favorite_places, all）
        """
        return f"get_family_info called with {category}"

    @tool
    def create_calendar_event(
        summary: str,
        date: str,
        start_time: str = None,
        end_time: str = None,
        description: str = None,
        location: str = None,
    ) -> str:
        """Googleカレンダーに新しい予定を登録します。

        Args:
            summary: 予定のタイトル
            date: 予定の日付（YYYY-MM-DD形式、例: 2026-01-25）
            start_time: 開始時刻（HH:MM形式、例: 14:30）。省略時は終日予定
            end_time: 終了時刻（HH:MM形式、例: 15:30）。省略時は開始から1時間後
            description: 予定の説明（任意）
            location: 場所（任意）
        """
        return f"create_calendar_event called with {summary}"

    @tool
    def web_search(
        query: str,
        search_type: str = "general",
        location: str = None,
    ) -> str:
        """インターネットで情報を検索します。営業時間、ニュース、店舗情報など一般的な質問に回答できます。

        Args:
            query: 検索したい内容や質問（例: 高の原イオンの営業時間、最近のニュース、子連れで行けるカフェ）
            search_type: 検索の種類（general=一般検索、business_hours=営業時間、route=経路、news=ニュース、restaurant=飲食店）
            location: 場所（経路検索や店舗検索時に使用）
        """
        return f"web_search called with {query}"

    @tool
    def set_reminder(
        message: str,
        date: str,
        time: str,
        repeat: str = "none",
        repeat_day: str = None,
    ) -> str:
        """指定した日時にリマインダーを設定します。一度きりや繰り返しの通知を設定できます。

        Args:
            message: リマインダーのメッセージ（例: 電話をする、薬を飲む）
            date: リマインダーの日付（YYYY-MM-DD形式）
            time: リマインダーの時刻（HH:MM形式、例: 10:00）
            repeat: 繰り返し設定（none=一度のみ、daily=毎日、weekly=毎週、monthly=毎月）
            repeat_day: 毎週リマインダーの場合の曜日（mon, tue, wed, thu, fri, sat, sun）
        """
        return f"set_reminder called with {message}"

    @tool
    def list_reminders() -> str:
        """設定されているリマインダーの一覧を表示します。"""
        return "list_reminders called"

    @tool
    def delete_reminder(reminder_id: str) -> str:
        """指定したIDのリマインダーを削除します。

        Args:
            reminder_id: 削除するリマインダーのID
        """
        return f"delete_reminder called with {reminder_id}"

    @tool
    def add_shopping_item(
        name: str,
        quantity: str = None,
        category: str = None,
        note: str = None,
    ) -> str:
        """買い物リストにアイテムを追加します。

        Args:
            name: 商品名（例: 牛乳、卵、食パン）
            quantity: 数量（例: 2本、1パック）
            category: カテゴリ（食品、野菜・果物、肉・魚、乳製品、飲料、調味料、日用品、洗剤・衛生用品、ベビー用品、医薬品、その他）
            note: メモ（例: 特売品、〇〇用）
        """
        return f"add_shopping_item called with {name}"

    @tool
    def list_shopping(category: str = None) -> str:
        """買い物リストを表示します。

        Args:
            category: カテゴリでフィルタ（省略時は全件）
        """
        return "list_shopping called"

    @tool
    def remove_shopping_item(item: str) -> str:
        """買い物リストからアイテムを削除します。

        Args:
            item: 削除する商品名またはID
        """
        return f"remove_shopping_item called with {item}"

    @tool
    def search_route(
        origin: str,
        destination: str,
        departure_time: str = None,
        arrival_time: str = None,
        date: str = None,
        search_type: str = "normal",
    ) -> str:
        """電車・バスの経路や時刻を検索します。

        Args:
            origin: 出発地（駅名や地名、例: 木津駅、高の原）
            destination: 目的地（駅名や地名、例: 京都駅、奈良駅）
            departure_time: 出発時刻（HH:MM形式）。省略時は現在時刻
            arrival_time: 到着希望時刻（HH:MM形式）。指定時はこの時刻に着くルートを検索
            date: 日付（YYYY-MM-DD形式または「明日」「今日」）
            search_type: 検索種類（normal=通常、last_train=終電、first_train=始発）
        """
        return f"search_route called from {origin} to {destination}"

    @tool
    def suggest_recipe(
        ingredients: str = None,
        dish_type: str = None,
        servings: int = 4,
        cooking_time: str = None,
        dietary_restrictions: str = None,
        request: str = None,
    ) -> str:
        """材料や条件からレシピを提案します。冷蔵庫にある材料で作れるレシピや、特定の料理のレシピを検索できます。

        Args:
            ingredients: 使いたい材料（カンマ区切り、例: 鶏肉, 玉ねぎ, じゃがいも）
            dish_type: 料理の種類（例: 和食、洋食、中華、主菜、副菜、スープ）
            servings: 何人前か（デフォルト: 4人前）
            cooking_time: 調理時間（quick=15分以内、normal=30分程度、long=1時間以上）
            dietary_restrictions: 食事制限（例: ベジタリアン、アレルギー食材、低カロリー）
            request: 具体的なリクエスト（例: 子供が喜ぶ料理、作り置きできるもの）
        """
        return f"suggest_recipe called with {ingredients}"

    @tool
    def search_nearby_store(
        store_type: str = None,
        product: str = None,
        area: str = None,
        requirements: str = None,
    ) -> str:
        """木津川市・奈良市周辺で店舗を検索します。スーパー、ドラッグストア、ホームセンター、飲食店などを探せます。

        Args:
            store_type: 店舗の種類（例: スーパー、ドラッグストア、ホームセンター、カフェ、レストラン、病院、公園）
            product: 探している商品やサービス（例: おむつ、子供服、文房具）
            area: エリア（例: 高の原、木津川台、精華町）。省略時は木津川市周辺
            requirements: 追加の要件（例: 駐車場あり、子連れOK、24時間営業）
        """
        return f"search_nearby_store called with {store_type}"

    @tool
    def track_package(
        tracking_number: str,
        carrier: str = "auto",
    ) -> str:
        """荷物の配送状況を追跡します。ヤマト運輸、佐川急便、日本郵便などの追跡番号から配送状況を確認できます。

        Args:
            tracking_number: 追跡番号（伝票番号）
            carrier: 配送業者（yamato=ヤマト運輸、sagawa=佐川急便、japanpost=日本郵便、auto=自動判定）
        """
        return f"track_package called with {tracking_number}"

    @tool
    def add_housework_task(
        name: str,
        category: str = "その他",
        interval_days: int = 0,
        note: str = None,
    ) -> str:
        """定期的な家事タスクを登録します。エアコンフィルター掃除、換気扇掃除などのメンテナンスタスクを管理できます。

        Args:
            name: タスク名（例: エアコンフィルター掃除、浴室カビ取り）
            category: カテゴリ（掃除、洗濯、料理、買い出し、住宅メンテナンス、家電メンテナンス等）
            interval_days: 繰り返し間隔（日数）。0=繰り返しなし、7=毎週、30=毎月、90=3ヶ月毎
            note: メモ
        """
        return f"add_housework_task called with {name}"

    @tool
    def done_housework(task: str) -> str:
        """家事タスクを完了としてマークします。タスク名またはIDで指定できます。

        Args:
            task: 完了したタスク名またはID（例: エアコンフィルター掃除）
        """
        return f"done_housework called with {task}"

    @tool
    def list_housework(
        category: str = None,
        due_only: bool = False,
    ) -> str:
        """家事タスクの一覧を表示します。期限切れのタスクも確認できます。

        Args:
            category: カテゴリでフィルタ（省略時は全件）
            due_only: trueの場合、期限切れのタスクのみ表示
        """
        return "list_housework called"

    @tool
    def control_light(room: str, action: str) -> str:
        """部屋の照明を制御します。ON/OFFを切り替えられます。

        Args:
            room: 部屋名（書斎、リビング、寝室、子供部屋、廊下）
            action: on=点灯、off=消灯
        """
        return f"control_light called: {room} {action}"

    @tool
    def control_climate(
        room: str,
        action: str,
        temperature: int = None,
        mode: str = "cool",
    ) -> str:
        """部屋のエアコンを制御します。ON/OFF、温度設定、モード切替ができます。

        Args:
            room: 部屋名（書斎、リビング、寝室、子供部屋）
            action: on=運転開始、off=停止
            temperature: 設定温度（16-30）
            mode: 運転モード（cool=冷房、heat=暖房、dry=除湿、fan_only=送風）
        """
        return f"control_climate called: {room} {action}"

    @tool
    def get_room_environment(room: str = "all") -> str:
        """部屋の温度・湿度などの環境情報を取得します。

        Args:
            room: 部屋名（書斎、リビング、寝室、子供部屋、all=全部屋）
        """
        return f"get_room_environment called: {room}"

    @tool
    def smart_home_speak(message: str, room: str = "リビング") -> str:
        """スマートスピーカーから音声でメッセージを伝えます。

        Args:
            message: 伝えるメッセージ
            room: スピーカーがある部屋（書斎、リビング、子供部屋）
        """
        return f"smart_home_speak called: {message}"

    @tool
    def record_expense(
        amount: int,
        description: str = None,
        category: str = None,
        date: str = None,
        payment_method: str = None,
    ) -> str:
        """支出を記録します。買い物や支払いの金額を家計簿に記録できます。

        Args:
            amount: 金額（円）
            description: 内容や購入場所（例: スーパーで食材、病院代）
            category: カテゴリ（食費、日用品、交通費、医療費、教育費、娯楽費、衣服費、通信費、水道光熱費、住居費、保険料、子供関連、その他）
            date: 日付（YYYY-MM-DD形式、省略時は今日）
            payment_method: 支払い方法（現金、クレジットカード、デビットカード、電子マネー、QRコード決済、銀行振込）
        """
        return f"record_expense called: {amount}"

    @tool
    def record_income(
        amount: int,
        description: str = None,
        category: str = "その他収入",
        date: str = None,
    ) -> str:
        """収入を記録します。給与や児童手当などの入金を記録できます。

        Args:
            amount: 金額（円）
            description: 内容（例: 給与、児童手当）
            category: カテゴリ（給与、副業、児童手当、その他収入）
            date: 日付（YYYY-MM-DD形式、省略時は今日）
        """
        return f"record_income called: {amount}"

    @tool
    def get_expense_summary(year: int = None, month: int = None) -> str:
        """月ごとの家計簿サマリーを表示します。収支やカテゴリ別支出を確認できます。

        Args:
            year: 年（省略時は今年）
            month: 月（1-12、省略時は今月）
        """
        return "get_expense_summary called"

    @tool
    def list_expenses(limit: int = 10) -> str:
        """最近の支出・収入記録を一覧表示します。

        Args:
            limit: 表示件数（デフォルト10件）
        """
        return "list_expenses called"

    @tool
    def get_school_info(child: str = None) -> str:
        """子供の学校・保育園情報を取得します。開園時間、連絡先などを確認できます。

        Args:
            child: 子供の名称（お嬢様、坊ちゃま）
        """
        return f"get_school_info called: {child}"

    @tool
    def get_school_events(days: int = 30) -> str:
        """学校・保育園の行事予定を取得します。運動会、お遊戯会などの予定を確認できます。

        Args:
            days: 何日先まで取得するか（デフォルト30日）
        """
        return "get_school_events called"

    @tool
    def get_school_items(item_type: str = "daily") -> str:
        """学校・保育園の持ち物リストを取得します。毎日・週ごと・特別な持ち物を確認できます。

        Args:
            item_type: 持ち物タイプ（daily=毎日、weekly=週ごと、special=特別）
        """
        return f"get_school_items called: {item_type}"

    # ========================================
    # 健康記録ツール
    # ========================================

    @tool
    def record_symptom(
        person: str, symptom: str, temperature: float = None, notes: str = ""
    ) -> str:
        """家族の症状・体調不良を記録します。体温も記録できます。

        Args:
            person: 対象者（旦那様、奥様、お嬢様など）
            symptom: 症状（例: 発熱、咳、鼻水、腹痛）
            temperature: 体温（省略可）
            notes: 備考（省略可）
        """
        return f"record_symptom called: {person}, {symptom}"

    @tool
    def record_hospital_visit(
        person: str,
        hospital: str,
        reason: str,
        diagnosis: str = "",
        prescription: str = "",
        next_visit: str = "",
    ) -> str:
        """通院記録を追加します。病院名、診断結果、処方薬などを記録できます。

        Args:
            person: 対象者（旦那様、奥様、お嬢様など）
            hospital: 病院名
            reason: 受診理由
            diagnosis: 診断結果（省略可）
            prescription: 処方薬（省略可）
            next_visit: 次回予約日（省略可）
        """
        return f"record_hospital_visit called: {person}, {hospital}"

    @tool
    def get_health_info(person: str = "") -> str:
        """家族の健康情報を取得します。アレルギー、持病、かかりつけ病院などを確認できます。

        Args:
            person: 対象者（省略時は全員）
        """
        return f"get_health_info called: {person}"

    @tool
    def get_health_records(
        person: str = "", record_type: str = "", days: int = 30
    ) -> str:
        """健康記録（症状、通院、服薬など）を取得します。

        Args:
            person: 対象者（省略時は全員）
            record_type: 記録タイプ（symptom, hospital, medicine, checkup）省略時は全タイプ
            days: 何日前までの記録を取得するか
        """
        return f"get_health_records called: {person}, {record_type}, {days}"

    return [
        get_calendar_events,
        get_weather,
        search_events,
        get_life_info,
        get_today_info,
        get_family_info,
        create_calendar_event,
        web_search,
        set_reminder,
        list_reminders,
        delete_reminder,
        add_shopping_item,
        list_shopping,
        remove_shopping_item,
        search_route,
        suggest_recipe,
        search_nearby_store,
        track_package,
        add_housework_task,
        done_housework,
        list_housework,
        control_light,
        control_climate,
        get_room_environment,
        smart_home_speak,
        record_expense,
        record_income,
        get_expense_summary,
        list_expenses,
        get_school_info,
        get_school_events,
        get_school_items,
        record_symptom,
        record_hospital_visit,
        get_health_info,
        get_health_records,
    ]


# =============================================================================
# Graph Configuration
# =============================================================================


class ButlerGraphConfig:
    """グラフ設定を保持するクラス"""

    def __init__(
        self,
        tool_executor: ToolExecutor | None = None,
        butler_name: str = "黒田",
        model: str = "claude-sonnet-4-20250514",
        max_retries: int = 2,
    ):
        self.tool_executor = tool_executor
        self.butler_name = butler_name
        self.model = model
        self.max_retries = max_retries

        # LLMを初期化（環境変数ANTHROPIC_API_KEYを自動的に使用）
        self.llm = ChatAnthropic(
            model=model,
            max_tokens=2048,
        )

        # ツールをバインド
        self.tools = create_langchain_tools()
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        logger.info(
            "ButlerGraphConfig initialized",
            model=model,
            tools_count=len(self.tools),
        )


# グローバル設定（compile時に設定）
_config: ButlerGraphConfig | None = None


def set_config(config: ButlerGraphConfig) -> None:
    """グラフ設定をセット"""
    global _config
    _config = config


def get_config() -> ButlerGraphConfig:
    """グラフ設定を取得"""
    global _config
    if _config is None:
        _config = ButlerGraphConfig()
    return _config


# =============================================================================
# Node Functions
# =============================================================================


def agent_node(state: AgentState) -> dict:
    """エージェントノード: Claude APIを呼び出してツール使用を判断

    LangChain ChatAnthropicを使用してClaudeを呼び出します。
    ツール呼び出しが必要な場合はtool_callsを含むAIMessageを返します。
    """
    config = get_config()
    logger.info("Agent node processing", messages_count=len(state["messages"]))

    # システムプロンプトを構築
    family_context = ""
    if state.get("user_context"):
        ctx = state["user_context"]
        if ctx.get("family_context"):
            family_context = f"## 追加コンテキスト\n{ctx['family_context']}"

    system_prompt = BUTLER_SYSTEM_PROMPT.format(
        butler_name=config.butler_name,
        family_context=family_context,
        today=datetime.now().strftime("%Y年%m月%d日(%A)"),
    )

    try:
        # Claude APIを呼び出し
        response = config.llm_with_tools.invoke(
            state["messages"],
            config={"configurable": {"system_message": system_prompt}},
        )

        logger.info(
            "Agent response received",
            has_tool_calls=(
                bool(response.tool_calls) if hasattr(response, "tool_calls") else False
            ),
        )

        return {"messages": [response], "error": None}

    except Exception as e:
        logger.error("Agent node failed", error=str(e))
        error_message = AIMessage(
            content=f"恐れ入ります、執事の{config.butler_name}でございます。"
            "ただいま処理に問題が発生いたしました。"
        )
        return {"messages": [error_message], "error": str(e)}


async def tools_node(state: AgentState) -> dict:
    """ツールノード: ToolExecutorを使用してツールを実行

    AgentのAIMessageからtool_callsを抽出し、
    既存のToolExecutorで実行してToolMessageを返します。
    """
    config = get_config()
    logger.info("Tools node processing")

    # 最後のAIメッセージからツール呼び出しを取得
    last_message = state["messages"][-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.warning("No tool calls found in last message")
        return {"messages": []}

    tool_messages = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        logger.info(f"Executing tool: {tool_name}", args=tool_args)

        if config.tool_executor:
            # 既存のToolExecutorを使用
            result = await config.tool_executor.execute(
                tool_name=tool_name,
                tool_input=tool_args,
                tool_use_id=tool_id,
            )
            content = result.content
        else:
            # ToolExecutorがない場合はモック応答
            content = f"[Mock] {tool_name} executed with {tool_args}"
            logger.warning("ToolExecutor not configured, using mock response")

        # ToolMessageを作成
        tool_message = ToolMessage(
            content=content,
            tool_call_id=tool_id,
        )
        tool_messages.append(tool_message)

        logger.info(f"Tool {tool_name} completed", result_length=len(content))

    return {"messages": tool_messages}


def validation_node(state: AgentState) -> dict:
    """バリデーションノード: 出力品質を検証

    最終応答が執事口調になっているかチェックします。
    問題があればHumanMessageを追加してリトライを促します。
    """
    config = get_config()
    logger.info("Validation node processing")

    # 最後のAIメッセージを取得
    last_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            last_message = msg
            break

    if not last_message:
        logger.warning("No AI message found for validation")
        return {"error": None}

    content = last_message.content

    # 簡易的な執事口調チェック
    butler_indicators = [
        "ございます",
        "くださいませ",
        "いたします",
        "かしこまりました",
        "恐れ入ります",
        "でございます",
        "存じます",
        "差し上げます",
    ]

    has_butler_tone = any(indicator in content for indicator in butler_indicators)

    current_retry = state.get("retry_count", 0)

    if not has_butler_tone and current_retry < config.max_retries:
        logger.info("Response lacks butler tone, requesting retry")
        # リトライ理由をメッセージ履歴に追加し、Claudeが認識できるようにする
        feedback = HumanMessage(
            content=(
                "【口調修正依頼】先ほどの応答内容はそのままに、執事口調に修正してください。"
                "「〜でございます」「〜くださいませ」「〜いたします」などの丁寧な表現を使い、"
                "執事「黒田」としてふさわしい口調で応答し直してください。"
                "内容を省略せず、情報量はそのまま維持してください。"
            )
        )
        return {
            "messages": [feedback],
            "error": "執事口調が不足しています。",
            "retry_count": current_retry + 1,
        }

    logger.info("Validation passed", has_butler_tone=has_butler_tone)
    return {"error": None}


# =============================================================================
# Conditional Edges (ルーティングロジック)
# =============================================================================


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """エージェントノード後の分岐を決定

    - ツール呼び出しが必要 → "tools"
    - 直接応答可能 → "end"
    """
    last_message = state["messages"][-1] if state["messages"] else None

    if (
        last_message
        and isinstance(last_message, AIMessage)
        and hasattr(last_message, "tool_calls")
        and last_message.tool_calls
    ):
        logger.info("Routing to tools node")
        return "tools"

    logger.info("Routing to end (no tool calls)")
    return "end"


def should_retry(state: AgentState) -> Literal["agent", "end"]:
    """バリデーション後の分岐を決定

    - 品質に問題あり → "agent" (リトライ)
    - 問題なし → "end"
    """
    if state.get("error"):
        logger.info("Validation failed, routing to agent for retry")
        return "agent"

    logger.info("Validation passed, routing to end")
    return "end"


# =============================================================================
# Graph Builder
# =============================================================================


def create_butler_graph() -> StateGraph:
    """執事エージェントのグラフを構築

    グラフ構造（ReActパターン + Validation）:
    ```
    START → agent ─┬─→ tools ─→ agent (loop)
                   │
                   └─→ validation ─┬─→ END
                                   │
                                   └─→ agent (retry)
    ```
    """
    # グラフを作成
    graph = StateGraph(AgentState)

    # ノードを追加
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("validation", validation_node)

    # エントリポイント
    graph.add_edge(START, "agent")

    # エージェント後の条件分岐
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": "validation",
        },
    )

    # ツール実行後はエージェントに戻る（ReActループ）
    graph.add_edge("tools", "agent")

    # バリデーション後の条件分岐
    graph.add_conditional_edges(
        "validation",
        should_retry,
        {
            "agent": "agent",
            "end": END,
        },
    )

    logger.info("Butler graph created")
    return graph


def compile_butler_graph(
    tool_executor: ToolExecutor | None = None,
    butler_name: str = "黒田",
    model: str = "claude-sonnet-4-20250514",
):
    """グラフをコンパイルして実行可能にする

    Args:
        tool_executor: ツール実行器（既存のToolExecutorを使用）
        butler_name: 執事の名前
        model: 使用するClaudeモデル

    Returns:
        CompiledGraph: コンパイル済みグラフ
    """
    # 設定を初期化
    config = ButlerGraphConfig(
        tool_executor=tool_executor,
        butler_name=butler_name,
        model=model,
    )
    set_config(config)

    # グラフを作成してコンパイル
    graph = create_butler_graph()
    compiled = graph.compile()

    logger.info("Butler graph compiled", model=model)
    return compiled


# =============================================================================
# Simple Example (学習用)
# =============================================================================


def create_simple_graph() -> StateGraph:
    """シンプルなグラフ（学習用）

    最も基本的な構造:
    START → process → END
    """

    class SimpleState(TypedDict):
        input: str
        output: str

    def process(state: SimpleState) -> dict:
        return {"output": f"処理結果: {state['input']}"}

    graph = StateGraph(SimpleState)
    graph.add_node("process", process)
    graph.add_edge(START, "process")
    graph.add_edge("process", END)

    return graph


# =============================================================================
# Visualization Helper
# =============================================================================


def get_graph_mermaid(graph: StateGraph) -> str:
    """グラフをMermaid形式で出力（可視化用）"""
    try:
        compiled = graph.compile()
        return compiled.get_graph().draw_mermaid()
    except Exception as e:
        logger.error(f"Failed to generate Mermaid diagram: {e}")
        return ""


# =============================================================================
# Execution Helper
# =============================================================================


async def run_butler_agent(
    message: str,
    tool_executor: ToolExecutor | None = None,
    butler_name: str = "黒田",
    user_context: dict[str, Any] | None = None,
    images: list[dict] | None = None,
) -> str:
    """執事エージェントを実行

    Args:
        message: ユーザーからのメッセージ
        tool_executor: ツール実行器
        butler_name: 執事の名前
        user_context: ユーザーコンテキスト
        images: 添付画像のリスト（base64エンコード済み）

    Returns:
        str: 執事からの応答
    """
    # グラフをコンパイル
    graph = compile_butler_graph(
        tool_executor=tool_executor,
        butler_name=butler_name,
    )

    # メッセージ内容を構築
    if images:
        # 画像がある場合はマルチモーダルメッセージを構築
        # LangChain ChatAnthropicはAnthropicネイティブの画像フォーマットを使用
        content = []

        # テキスト部分（ユーザーのメッセージがあればそのまま使用）
        if message:
            user_text = message
        else:
            user_text = ""

        # 画像分析の指示を追加（イベント情報なら自動登録を促す）
        instruction = """この画像を分析してください。
イベント・予定・チラシ・案内等の場合は、create_calendar_eventツールで即座にカレンダーに登録してください。
確認は不要です。

【回答に必ず含める情報】
イベント情報の場合、以下を必ず回答に含めてください：
1. 日時（開始時刻・終了時刻）
2. 場所（住所も含む）
3. 参加費・料金（大人・子供など区分があれば全て）
4. 予約要否（事前予約が必要かどうか）
5. 持ち物・準備物（服装指定があれば含む）
6. 問い合わせ先（電話番号・SNSなど）

画像から読み取れる情報を漏れなく伝えてください。"""

        if user_text:
            content.append({"type": "text", "text": f"{user_text}\n\n{instruction}"})
        else:
            content.append({"type": "text", "text": instruction})

        # 画像部分（Anthropicネイティブフォーマット）
        for img in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img["media_type"],
                        "data": img["data"],
                    },
                }
            )

        human_message = HumanMessage(content=content)
    else:
        human_message = HumanMessage(content=message)

    # 初期状態を構築
    initial_state = {
        "messages": [human_message],
        "user_context": user_context or {},
        "retry_count": 0,
        "error": None,
    }

    # グラフを実行
    result = await graph.ainvoke(initial_state)

    # 最後のAIメッセージを取得
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content

    return "恐れ入ります、応答を生成できませんでした。"


if __name__ == "__main__":
    # テスト実行
    print("=== Simple Graph ===")
    simple = create_simple_graph()
    print(get_graph_mermaid(simple))

    print("\n=== Butler Graph ===")
    butler = create_butler_graph()
    print(get_graph_mermaid(butler))
