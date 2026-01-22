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
- 必要に応じてツールを使用して情報を取得

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
    問題があればerrorを設定してリトライを促します。
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
        return {
            "error": "執事口調が不足しています。より丁寧な口調で応答してください。",
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
        content = []

        # テキスト部分
        if message:
            content.append({"type": "text", "text": message})

        # 画像部分
        for img in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{img['media_type']};base64,{img['data']}"
                    },
                }
            )

        # 画像分析用のヒントを追加
        if not message or "イベント" not in message:
            content.append(
                {
                    "type": "text",
                    "text": "\n\n画像にイベントや予定の情報が含まれている場合は、日時・場所・内容を抽出してお知らせください。"
                    "カレンダーへの登録をご希望の場合はお申し付けください。",
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
