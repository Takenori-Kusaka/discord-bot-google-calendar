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

        # イベント情報をインデックス付きで変換（IDではなくインデックスで照合）
        events_for_prompt = []
        for i, e in enumerate(events):
            event_dict = {
                "index": i,
                "summary": e.summary,
                "start": e.start.isoformat(),
                "end": e.end.isoformat(),
                "all_day": e.all_day,
            }
            if e.location:
                event_dict["location"] = e.location
            if e.description:
                event_dict["description"] = e.description
            events_for_prompt.append(event_dict)

        events_json = json.dumps(events_for_prompt, ensure_ascii=False, indent=2)

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
重要な予定のインデックス番号をJSON配列で返してください。例: [0, 2]
重要な予定がない場合は空の配列を返してください: []
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            # レスポンスからインデックスリストを抽出
            content = response.content[0].text
            # JSON部分を抽出
            start_idx = content.find("[")
            end_idx = content.rfind("]") + 1
            if start_idx >= 0 and end_idx > start_idx:
                important_indices = json.loads(content[start_idx:end_idx])
            else:
                important_indices = []

            # 整数に変換し、範囲外のインデックスを除外
            valid_indices = [
                int(i)
                for i in important_indices
                if isinstance(i, (int, str)) and 0 <= int(i) < len(events)
            ]

            logger.info(
                "Filtered important events",
                total=len(events),
                important=len(valid_indices),
            )

            # インデックスでフィルタリング
            return [events[i] for i in valid_indices]

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
            logger.warning("No search results provided for event extraction")
            return []

        # 今週末の日付を計算
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Asia/Tokyo")
        now = datetime.now(tz)
        # 今週の土曜日を計算 (weekday: 月=0, 土=5)
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.hour >= 18:
            # 土曜の18時以降は来週末
            days_until_saturday = 7
        saturday = now + timedelta(days=days_until_saturday)
        sunday = saturday + timedelta(days=1)

        saturday_str = saturday.strftime("%Y/%m/%d")
        sunday_str = sunday.strftime("%Y/%m/%d")
        saturday_short = saturday.strftime("%m/%d")
        sunday_short = sunday.strftime("%m/%d")

        logger.info(
            f"Extracting events for weekend: {saturday_str}〜{sunday_str}, "
            f"search_results_count={len(search_results)}"
        )

        # 検索結果をテキストに変換（最大40件に制限してトークン節約）
        limited_results = search_results[:40]
        results_text = "\n\n".join(
            [
                f"【{r.get('query', '')}】\n"
                f"タイトル: {r.get('title', '')}\n"
                f"内容: {r.get('snippet', '')}\n"
                f"URL: {r.get('link', '')}"
                for r in limited_results
            ]
        )

        prompt = f"""あなたは地域イベント情報を抽出するアシスタントです。
以下の検索結果から、今週末に開催されるイベント情報を抽出してください。

## 今週末の日付
- 今日: {now.strftime('%Y年%m月%d日(%a)')}
- 対象日: {saturday_str}(土) 〜 {sunday_str}(日)

## 検索結果（{len(limited_results)}件）
{results_text}

## 抽出ルール
1. 今週末（{saturday_str}〜{sunday_str}）に開催されるイベントを抽出
2. 日程が明確に記載されていないイベントも、週末開催の可能性があれば含める
3. 子供連れで参加できそうなイベントを優先
4. 同じイベントの重複は除外

## 出力形式
必ずJSON配列のみを出力してください。説明文は不要です。
イベントが見つからない場合でも空配列[]を返してください。

```json
[
  {{
    "title": "イベント名",
    "date": "{saturday_short}(土) 10:00〜",
    "location": "開催場所",
    "description": "概要（50文字以内）",
    "target_audience": "全年齢/子供向け/大人向け",
    "url": "情報元URL"
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
            logger.debug(f"Claude response (first 500 chars): {content[:500]}")

            # JSON部分を抽出
            start_idx = content.find("[")
            end_idx = content.rfind("]") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                try:
                    events = json.loads(json_str)
                except json.JSONDecodeError as je:
                    logger.error(f"JSON parse error: {je}, json_str={json_str[:200]}")
                    events = []
            else:
                logger.warning(
                    f"No JSON array found in response. "
                    f"start_idx={start_idx}, end_idx={end_idx}, "
                    f"content_preview={content[:300]}"
                )
                events = []

            logger.info(f"Extracted {len(events)} events from search results")
            return events

        except Exception as e:
            logger.error(f"Failed to extract events: {e}", exc_info=True)
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

    async def generate_life_info_summary(
        self,
        law_items: list[dict],
    ) -> list[dict]:
        """法令情報をClaude APIで要約・影響度判定

        Args:
            law_items: 法令情報のリスト（title, description, source_url等）

        Returns:
            list[dict]: 要約・影響度判定結果
        """
        if not law_items:
            return []

        laws_json = json.dumps(law_items, ensure_ascii=False, indent=2)

        prompt = f"""以下の法令・制度リストについて、家族への影響度を判定し要約してください。

## 家族構成
- 旦那様（35歳、IT企業勤務、育休中 2026年1月26日〜9月18日）
- 奥様（34歳）
- お嬢様（4歳、保育園）
- 坊ちゃま（0歳）
- 京都府木津川市在住

## 法令・制度リスト
{laws_json}

## 判定ルール
1. 各法令について、この家族の日常生活に関係する内容を要約してください
2. 最近の主な改正ポイントがあれば含めてください
3. impact_level は以下の基準で判定:
   - "high": 手続きが必要、金銭的影響がある、期限がある
   - "medium": 知っておくと役立つ、今後影響する可能性がある
   - "low": 直接的な影響は小さい
4. requires_action: 何か手続きや対応が必要な場合はtrue

## 出力形式
必ずJSON配列のみを出力してください。説明文は不要です。

```json
[
  {{
    "title": "法令名（入力と同じ）",
    "impact_level": "high|medium|low",
    "summary": "この法令の概要と最近の改正ポイント（2-3文、100文字程度）",
    "family_relevance": "この家族にどう関係するか（1文、50文字程度）",
    "requires_action": false
  }}
]
```"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text
            logger.debug(
                f"Life info summary response (first 500 chars): {content[:500]}"
            )

            # JSON部分を抽出
            start_idx = content.find("[")
            end_idx = content.rfind("]") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                try:
                    results = json.loads(json_str)
                    logger.info(f"Generated life info summary for {len(results)} items")
                    return results
                except json.JSONDecodeError as je:
                    logger.error(f"JSON parse error: {je}, json_str={json_str[:200]}")
                    return []
            else:
                logger.warning(f"No JSON array found in life info summary response")
                return []

        except Exception as e:
            logger.error(f"Failed to generate life info summary: {e}", exc_info=True)
            return []

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
                logger.error(
                    f"Error in chat_with_tools iteration {iteration}", error=str(e)
                )
                break

        # エラー時のフォールバック
        return (
            f"恐れ入ります、執事の{butler_name}でございます。"
            "ただいま処理に問題が発生いたしました。"
            "しばらくしてから再度お申し付けくださいませ。"
        )
