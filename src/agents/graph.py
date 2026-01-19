"""LangGraph ベースのエージェント実装"""

from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from ..utils.logger import get_logger

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

    # 現在のエージェント/ノード
    current_node: str

    # ツール実行結果
    tool_results: dict[str, Any]

    # ユーザー情報（家族コンテキストなど）
    user_context: dict[str, Any]

    # エラー情報
    error: str | None


# =============================================================================
# Node Functions
# =============================================================================


def router_node(state: AgentState) -> dict:
    """ルーターノード: ユーザー意図を判断し、適切なノードにルーティング

    これが「オーケストレーター」の役割を担います。
    """
    logger.info("Router node processing", messages_count=len(state["messages"]))

    # 最新のユーザーメッセージを取得
    last_message = state["messages"][-1] if state["messages"] else None

    if not last_message:
        return {"current_node": "respond", "error": "No message to process"}

    # ここでは単純にcurrent_nodeを更新
    # 実際のルーティングロジックはconditional_edgesで定義
    return {"current_node": "agent"}


def agent_node(state: AgentState) -> dict:
    """エージェントノード: LLMを呼び出してツール使用を判断

    このノードがClaude APIを呼び出し、ツール使用の判断を行います。
    """
    logger.info("Agent node processing")

    # ここにClaude API呼び出しロジックを実装
    # 今は placeholder
    return {"current_node": "tools"}


def tools_node(state: AgentState) -> dict:
    """ツールノード: ツールを実行

    LangGraphのToolNodeを使用するか、カスタム実装を使用できます。
    """
    logger.info("Tools node processing")

    # ツール実行ロジック
    return {"current_node": "respond"}


def respond_node(state: AgentState) -> dict:
    """応答ノード: 最終応答を生成

    ツール結果を統合し、執事口調で応答を生成します。
    """
    logger.info("Respond node processing")

    # 応答生成ロジック
    return {"current_node": END}


def validation_node(state: AgentState) -> dict:
    """バリデーションノード: 出力を検証

    フィードバックループの一部として、出力の品質を検証します。
    問題があれば agent_node に戻します。
    """
    logger.info("Validation node processing")

    # バリデーションロジック
    # 例: 応答が執事口調かどうかチェック
    return {"current_node": END}


# =============================================================================
# Conditional Edges (ルーティングロジック)
# =============================================================================


def should_continue(state: AgentState) -> Literal["tools", "respond", "end"]:
    """エージェントノード後の分岐を決定

    - ツール呼び出しが必要 → "tools"
    - 直接応答可能 → "respond"
    - 終了 → "end"
    """
    # メッセージからツール呼び出しの有無を判断
    last_message = state["messages"][-1] if state["messages"] else None

    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return "respond"


def should_retry(state: AgentState) -> Literal["agent", "end"]:
    """バリデーション後の分岐を決定

    - 品質に問題あり → "agent" (リトライ)
    - 問題なし → "end"
    """
    if state.get("error"):
        return "agent"
    return "end"


# =============================================================================
# Graph Builder
# =============================================================================


def create_butler_graph() -> StateGraph:
    """執事エージェントのグラフを構築

    グラフ構造:
    ```
    START → router → agent → tools → respond → validation → END
                       ↑                           │
                       └───────── (retry) ─────────┘
    ```
    """
    # グラフを作成
    graph = StateGraph(AgentState)

    # ノードを追加
    graph.add_node("router", router_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("respond", respond_node)
    graph.add_node("validation", validation_node)

    # エッジを追加（基本フロー）
    graph.add_edge(START, "router")
    graph.add_edge("router", "agent")

    # 条件付きエッジ（エージェント後の分岐）
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "respond": "respond",
            "end": END,
        },
    )

    # ツール実行後は応答ノードへ
    graph.add_edge("tools", "respond")

    # 応答後はバリデーションへ
    graph.add_edge("respond", "validation")

    # バリデーション後の条件付きエッジ（リトライループ）
    graph.add_conditional_edges(
        "validation",
        should_retry,
        {
            "agent": "agent",  # リトライ
            "end": END,
        },
    )

    logger.info("Butler graph created")
    return graph


def compile_butler_graph():
    """グラフをコンパイルして実行可能にする"""
    graph = create_butler_graph()
    compiled = graph.compile()
    logger.info("Butler graph compiled")
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


if __name__ == "__main__":
    # テスト実行
    print("=== Simple Graph ===")
    simple = create_simple_graph()
    print(get_graph_mermaid(simple))

    print("\n=== Butler Graph ===")
    butler = create_butler_graph()
    print(get_graph_mermaid(butler))
