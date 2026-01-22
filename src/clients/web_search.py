"""汎用Web検索クライアント

Perplexity APIを使用して、一般的な質問に対するWeb検索を実行します。
"""

import aiohttp

from ..utils.logger import get_logger

logger = get_logger(__name__)


class WebSearchClient:
    """汎用Web検索クライアント

    Perplexity APIを使用してリアルタイムのWeb情報を取得します。
    """

    def __init__(self, perplexity_api_key: str):
        """初期化

        Args:
            perplexity_api_key: Perplexity APIキー
        """
        self.api_key = perplexity_api_key
        self.api_url = "https://api.perplexity.ai/chat/completions"
        logger.info("Web search client initialized")

    async def search(self, query: str, context: str | None = None) -> str:
        """Web検索を実行

        Args:
            query: 検索クエリ
            context: 追加のコンテキスト情報（オプション）

        Returns:
            検索結果のテキスト
        """
        logger.info("Executing web search", query=query)

        # プロンプトを構築
        system_prompt = """あなたは家庭の執事をサポートするアシスタントです。
ユーザーの質問に対して、正確で最新の情報を提供してください。

回答のガイドライン:
- 簡潔かつ正確に回答してください
- 情報源がある場合は明記してください
- 日本語で回答してください
- 不確かな情報は「確認が必要」と明記してください"""

        user_prompt = query
        if context:
            user_prompt = f"{context}\n\n質問: {query}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url, headers=headers, json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            "Perplexity API error",
                            status=response.status,
                            error=error_text,
                        )
                        return (
                            f"Web検索に失敗しました（エラーコード: {response.status}）"
                        )

                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.info("Web search completed", result_length=len(content))
                    return content

        except aiohttp.ClientError as e:
            logger.error("Network error during web search", error=str(e))
            return (
                "ネットワークエラーが発生しました。しばらくしてから再度お試しください。"
            )
        except Exception as e:
            logger.error("Web search failed", error=str(e))
            return f"Web検索中にエラーが発生しました: {str(e)}"

    async def search_with_sources(self, query: str) -> dict:
        """ソース付きでWeb検索を実行

        Args:
            query: 検索クエリ

        Returns:
            {"content": 回答テキスト, "sources": ソースリスト}
        """
        logger.info("Executing web search with sources", query=query)

        system_prompt = """あなたは家庭の執事をサポートするアシスタントです。
ユーザーの質問に対して、正確で最新の情報を提供してください。

回答形式:
1. 質問への回答を日本語で提供
2. 参照した情報源があれば「【参考】」として列挙"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url, headers=headers, json=payload
                ) as response:
                    if response.status != 200:
                        return {
                            "content": f"Web検索に失敗しました（エラーコード: {response.status}）",
                            "sources": [],
                        }

                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]

                    # citations があれば取得
                    citations = data.get("citations", [])

                    return {"content": content, "sources": citations}

        except Exception as e:
            logger.error("Web search with sources failed", error=str(e))
            return {
                "content": f"Web検索中にエラーが発生しました: {str(e)}",
                "sources": [],
            }

    async def get_business_hours(self, place_name: str, location: str = "") -> str:
        """店舗・施設の営業時間を検索

        Args:
            place_name: 店舗・施設名
            location: 場所（オプション）

        Returns:
            営業時間情報
        """
        query = f"{place_name}の営業時間"
        if location:
            query = f"{location}の{place_name}の営業時間"

        return await self.search(query)

    async def get_route_info(
        self, origin: str, destination: str, mode: str = "車"
    ) -> str:
        """経路・所要時間を検索

        Args:
            origin: 出発地
            destination: 目的地
            mode: 移動手段（車、電車、徒歩）

        Returns:
            経路・所要時間情報
        """
        query = f"{origin}から{destination}まで{mode}でどのくらいかかりますか？所要時間とルートを教えてください。"
        return await self.search(query)

    async def get_news(self, topic: str = "", region: str = "") -> str:
        """ニュースを検索

        Args:
            topic: トピック（オプション）
            region: 地域（オプション）

        Returns:
            ニュース情報
        """
        if topic and region:
            query = f"{region}の{topic}に関する最新ニュースを教えてください。"
        elif topic:
            query = f"{topic}に関する最新ニュースを教えてください。"
        elif region:
            query = f"{region}の最新ニュースを教えてください。"
        else:
            query = "今日の主要ニュースを教えてください。"

        return await self.search(query)

    async def search_restaurant(
        self, cuisine: str = "", location: str = "", requirements: str = ""
    ) -> str:
        """レストラン・飲食店を検索

        Args:
            cuisine: 料理の種類（オプション）
            location: 場所（オプション）
            requirements: 条件（子連れOK、個室ありなど）

        Returns:
            レストラン情報
        """
        parts = []
        if location:
            parts.append(location)
        if cuisine:
            parts.append(cuisine)
        parts.append("おすすめの店")
        if requirements:
            parts.append(f"（{requirements}）")

        query = "".join(parts) + "を教えてください。"
        return await self.search(query)

    async def general_query(self, question: str) -> str:
        """一般的な質問に回答

        Args:
            question: 質問

        Returns:
            回答
        """
        return await self.search(question)
