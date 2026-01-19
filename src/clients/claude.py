"""Claude API クライアント"""

import json
from collections import deque
from datetime import datetime
from typing import Any, Optional

import anthropic

from ..utils.logger import get_logger
from .calendar import CalendarEvent

logger = get_logger(__name__)

# 会話履歴の最大保持数
MAX_CONVERSATION_HISTORY = 10


class ClaudeClient:
    """Claude API クライアント"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """初期化

        Args:
            api_key: Anthropic APIキー
            model: 使用するモデル名
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # 会話履歴（チャンネルごとに管理）
        self._conversation_history: dict[str, deque] = {}

        logger.info("Claude client initialized", model=model)

    def _get_conversation_history(self, channel: str) -> deque:
        """チャンネルの会話履歴を取得"""
        if channel not in self._conversation_history:
            self._conversation_history[channel] = deque(maxlen=MAX_CONVERSATION_HISTORY)
        return self._conversation_history[channel]

    def _add_to_history(self, channel: str, role: str, content: str) -> None:
        """会話履歴に追加"""
        history = self._get_conversation_history(channel)
        history.append({"role": role, "content": content})

    def clear_conversation_history(self, channel: Optional[str] = None) -> None:
        """会話履歴をクリア

        Args:
            channel: クリアするチャンネル（Noneの場合は全チャンネル）
        """
        if channel:
            if channel in self._conversation_history:
                self._conversation_history[channel].clear()
        else:
            self._conversation_history.clear()
        logger.info("Conversation history cleared", channel=channel)

    async def filter_important_events(
        self,
        events: list[CalendarEvent],
        ignore_patterns: list[str] | None = None,
        notify_patterns: list[str] | None = None,
    ) -> list[CalendarEvent]:
        """重要な予定をフィルタリング

        Args:
            events: イベントリスト
            ignore_patterns: 無視するパターン
            notify_patterns: 必ず通知するパターン

        Returns:
            list[CalendarEvent]: フィルタリングされたイベント
        """
        if not events:
            return []

        # イベント情報をJSON形式に変換
        events_json = json.dumps(
            [e.to_dict() for e in events],
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""あなたは家庭の執事として、ご主人様の予定を管理しています。
以下の予定リストから、本日特に注意が必要な予定をピックアップしてください。

## 判断基準

### 通知すべき予定
- 外出を伴う予定（通院、面談、イベント参加など）
- 時間が決まっている予定
- 忘れると困る予定（締切、予約など）
- 家族全員に関係する予定
{f"- 以下のキーワードを含む予定は必ず通知: {', '.join(notify_patterns)}" if notify_patterns else ""}

### 通知しない予定
- 単なるメモや備忘録
- 繰り返しのルーティン（「仕事」など曖昧なもの）
- 終日の背景的な予定
{f"- 以下のキーワードを含む予定は無視: {', '.join(ignore_patterns)}" if ignore_patterns else ""}

## 予定リスト
{events_json}

## 出力形式
重要な予定のIDをJSON配列で返してください。例: ["id1", "id2"]
予定がない場合は空の配列を返してください: []
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            # レスポンスからIDリストを抽出
            content = response.content[0].text
            # JSON部分を抽出
            start_idx = content.find("[")
            end_idx = content.rfind("]") + 1
            if start_idx >= 0 and end_idx > start_idx:
                important_ids = json.loads(content[start_idx:end_idx])
            else:
                important_ids = []

            logger.info(
                "Filtered important events",
                total=len(events),
                important=len(important_ids),
            )

            # IDでフィルタリング
            return [e for e in events if e.id in important_ids]

        except Exception as e:
            logger.error("Failed to filter events", error=str(e))
            # エラー時は全イベントを返す
            return events

    async def generate_butler_message(
        self,
        events: list[CalendarEvent],
        butler_name: str = "黒田",
    ) -> str:
        """執事口調のメッセージを生成

        Args:
            events: イベントリスト
            butler_name: 執事の名前

        Returns:
            str: 執事口調のメッセージ
        """
        if not events:
            return f"""旦那様、おはようございます。執事の{butler_name}でございます。

本日のご予定は特にございません。
どうぞごゆっくりお過ごしくださいませ。"""

        events_text = "\n".join(
            [
                f"- {e.start.strftime('%H:%M') if not e.all_day else '終日'}: {e.summary}"
                + (f"（{e.location}）" if e.location else "")
                for e in events
            ]
        )

        prompt = f"""あなたは日下家に仕える執事「{butler_name}」です。
丁寧で品のある執事口調で、朝の予定をお伝えするメッセージを作成してください。

## 口調の例
- 「旦那様、おはようございます。執事の{butler_name}でございます。」
- 「本日のご予定をお知らせいたします。」
- 「どうぞお気をつけてお出かけくださいませ。」

## 本日の予定
{events_text}

## 注意事項
- 各予定について簡潔にコメントを添えてください
- 外出の予定があれば、天気や準備についても一言添えてください
- 絵文字は使用しないでください
- 200文字程度に収めてください
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            message = response.content[0].text
            logger.info("Generated butler message", length=len(message))
            return message

        except Exception as e:
            logger.error("Failed to generate message", error=str(e))
            # エラー時はシンプルなメッセージを返す
            return f"""旦那様、おはようございます。執事の{butler_name}でございます。

本日のご予定をお知らせいたします。

{events_text}

どうぞよい一日をお過ごしくださいませ。"""

    async def extract_events_from_search(
        self,
        search_results: list[dict],
    ) -> list[dict]:
        """検索結果からイベント情報を抽出

        Args:
            search_results: 検索結果のリスト

        Returns:
            list[dict]: 抽出されたイベント情報
        """
        if not search_results:
            return []

        # 検索結果をテキストに変換
        results_text = "\n\n".join(
            [
                f"【{r.get('query', '')}】\n"
                f"タイトル: {r.get('title', '')}\n"
                f"内容: {r.get('snippet', '')}\n"
                f"URL: {r.get('link', '')}"
                for r in search_results
            ]
        )

        prompt = f"""以下の検索結果から、今週末（土曜・日曜）に開催されるイベント情報を抽出してください。

## 検索結果
{results_text}

## 抽出対象
- イベント名
- 開催日時
- 開催場所
- 概要（50文字程度）
- 対象年齢層（子供向け、大人向け、全年齢など）
- 情報元URL

## 出力形式
JSON配列で出力してください。イベントが見つからない場合は空配列を返してください。
```json
[
  {{
    "title": "イベント名",
    "date": "MM/DD(曜) HH:MM〜",
    "location": "場所",
    "description": "概要",
    "target_audience": "対象年齢層",
    "url": "URL"
  }}
]
```
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

            # JSON部分を抽出
            start_idx = content.find("[")
            end_idx = content.rfind("]") + 1
            if start_idx >= 0 and end_idx > start_idx:
                events = json.loads(content[start_idx:end_idx])
            else:
                events = []

            logger.info(f"Extracted {len(events)} events from search results")
            return events

        except Exception as e:
            logger.error(f"Failed to extract events: {e}")
            return []

    async def generate_event_recommendation(
        self,
        events: list[dict],
        butler_name: str = "黒田",
    ) -> str:
        """家族向けイベントおすすめメッセージを生成

        Args:
            events: イベント情報のリスト
            butler_name: 執事の名前

        Returns:
            str: おすすめメッセージ
        """
        if not events:
            return f"""旦那様、奥様、執事の{butler_name}でございます。

今週末の地域イベントを調査いたしましたが、
残念ながらお知らせできる情報が見つかりませんでした。

また来週、改めてご報告いたします。"""

        events_json = json.dumps(events, ensure_ascii=False, indent=2)

        prompt = f"""あなたは日下家に仕える執事「{butler_name}」です。
今週末の地域イベント情報を、ご家族にお伝えするメッセージを作成してください。

## 家族構成
- 旦那様（35歳）
- 奥様（34歳）
- お嬢様（4歳）
- 坊ちゃま（0歳）

## 今週末のイベント情報
{events_json}

## メッセージ作成ルール
1. 執事らしい丁寧な口調で
2. 4歳児が楽しめるイベントを優先的に紹介
3. 0歳児連れでも参加しやすいかコメント
4. 各イベントの簡単な説明とおすすめポイント
5. 絵文字は使用しない
6. 400文字程度に収める

## 出力形式
挨拶 → おすすめイベント紹介（優先度順）→ 締めの言葉
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            message = response.content[0].text
            logger.info("Generated event recommendation", length=len(message))
            return message

        except Exception as e:
            logger.error(f"Failed to generate recommendation: {e}")
            # エラー時はシンプルなメッセージ
            event_list = "\n".join(
                [f"- {e.get('title', '')}（{e.get('location', '')}）" for e in events]
            )
            return f"""旦那様、奥様、執事の{butler_name}でございます。

今週末の地域イベント情報をお知らせいたします。

{event_list}

詳細はリンク先をご確認くださいませ。"""

    async def chat(
        self,
        message: str,
        channel: str,
        butler_name: str = "黒田",
        family_context: Optional[str] = None,
    ) -> str:
        """対話形式でメッセージに応答

        Args:
            message: ユーザーからのメッセージ
            channel: チャンネル名（会話履歴管理用）
            butler_name: 執事の名前
            family_context: 家族情報コンテキスト

        Returns:
            str: 執事からの応答
        """
        # システムプロンプト
        system_prompt = f"""あなたは日下家に仕える執事「{butler_name}」です。

## あなたの役割
- 日下家の生活を総合的にサポートする執事
- 丁寧で品のある執事口調で応答
- 家族の喜びを自分の喜びとするホスピタリティ

## 口調の例
- 「かしこまりました。」
- 「恐れ入りますが、〜でございます。」
- 「ただいまお調べいたします。」
- 「どうぞご安心くださいませ。」

## 家族構成
- 旦那様（35歳、男性）
- 奥様（34歳、女性）
- お嬢様（4歳、女児）
- 坊ちゃま（0歳、男児）

## 地域情報
- 居住地: 京都府木津川市
- 近隣: 奈良市、精華町、高の原、けいはんな

{f"## 追加コンテキスト{chr(10)}{family_context}" if family_context else ""}

## 応答ルール
1. 簡潔に応答（200文字程度）
2. 絵文字は使用しない
3. 不明な点は正直に「存じ上げません」と答える
4. 危険な内容や不適切な依頼は丁重にお断りする
5. 今日は{datetime.now().strftime('%Y年%m月%d日(%A)')}です
"""

        # 会話履歴を取得
        history = self._get_conversation_history(channel)
        messages = list(history)

        # 新しいメッセージを追加
        messages.append({"role": "user", "content": message})

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
            )

            assistant_message = response.content[0].text

            # 会話履歴に追加
            self._add_to_history(channel, "user", message)
            self._add_to_history(channel, "assistant", assistant_message)

            logger.info(
                "Chat response generated",
                channel=channel,
                input_length=len(message),
                output_length=len(assistant_message),
            )

            return assistant_message

        except Exception as e:
            logger.error("Failed to generate chat response", error=str(e))
            return (
                f"恐れ入ります、執事の{butler_name}でございます。"
                "ただいま処理に問題が発生いたしました。"
                "しばらくしてから再度お申し付けくださいませ。"
            )

    async def chat_with_tools(
        self,
        message: str,
        channel: str,
        tools: list[dict],
        tool_executor,  # ToolExecutor
        butler_name: str = "黒田",
        family_context: Optional[str] = None,
        max_iterations: int = 5,
    ) -> str:
        """ツールを使用した対話形式でメッセージに応答

        Args:
            message: ユーザーからのメッセージ
            channel: チャンネル名（会話履歴管理用）
            tools: ツール定義のリスト
            tool_executor: ツール実行器
            butler_name: 執事の名前
            family_context: 家族情報コンテキスト
            max_iterations: ツール実行の最大反復回数

        Returns:
            str: 執事からの応答
        """
        # システムプロンプト
        system_prompt = f"""あなたは日下家に仕える執事「{butler_name}」です。

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

{f"## 追加コンテキスト{chr(10)}{family_context}" if family_context else ""}

## ツール使用ガイドライン
- 予定の確認 → get_calendar_events
- 天気予報 → get_weather
- 地域イベント → search_events
- 法改正・制度情報 → get_life_info
- 今日は何の日 → get_today_info
- ごみ出し・家族情報 → get_family_info

## 応答ルール
1. ツールで取得した情報を基に応答
2. 簡潔に応答（300文字程度）
3. 絵文字は使用しない
4. 不明な点は正直に「存じ上げません」と答える
5. 今日は{datetime.now().strftime('%Y年%m月%d日(%A)')}です
"""

        # 会話履歴を取得
        history = self._get_conversation_history(channel)
        messages = list(history)
        messages.append({"role": "user", "content": message})

        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            try:
                # Claude APIにツール付きで送信
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    system=system_prompt,
                    tools=tools,
                    messages=messages,
                )

                # レスポンスの終了理由を確認
                if response.stop_reason == "end_turn":
                    # 通常の応答（ツール呼び出しなし）
                    text_content = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            text_content += block.text

                    # 会話履歴に追加
                    self._add_to_history(channel, "user", message)
                    self._add_to_history(channel, "assistant", text_content)

                    logger.info(
                        "Chat with tools completed",
                        channel=channel,
                        iterations=iteration,
                        output_length=len(text_content),
                    )

                    return text_content

                elif response.stop_reason == "tool_use":
                    # ツール呼び出しを処理
                    assistant_content = response.content
                    messages.append({"role": "assistant", "content": assistant_content})

                    # ツールを実行
                    tool_results = []
                    for block in assistant_content:
                        if block.type == "tool_use":
                            logger.info(
                                f"Executing tool: {block.name}",
                                tool_input=block.input,
                            )

                            result = await tool_executor.execute(
                                tool_name=block.name,
                                tool_input=block.input,
                                tool_use_id=block.id,
                            )

                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": result.tool_use_id,
                                    "content": result.content,
                                    "is_error": result.is_error,
                                }
                            )

                    # ツール結果をメッセージに追加
                    messages.append({"role": "user", "content": tool_results})

                else:
                    # 予期しない終了理由
                    logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                    break

            except Exception as e:
                logger.error(f"Error in chat_with_tools iteration {iteration}", error=str(e))
                break

        # エラー時のフォールバック
        return (
            f"恐れ入ります、執事の{butler_name}でございます。"
            "ただいま処理に問題が発生いたしました。"
            "しばらくしてから再度お申し付けくださいませ。"
        )
