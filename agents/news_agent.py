import os
import httpx
import json
from typing import Dict, Any
from .base_agent import BaseAgent

async def get_news(category: str = "", query: str = "") -> str:
    """
    Perplexity APIを使用してニュース情報を取得する
    
    Args:
        category (str): ニュースカテゴリー（オプション）
        query (str): 検索クエリ（オプション）
    
    Returns:
        str: ニュース情報のJSON文字列
    """
    try:
        api_key = os.getenv('PERPLEXITY_API_KEY')
        if not api_key:
            return "Perplexity APIキーが設定されていません。"
        
        # プロンプトの構築
        if category:
            prompt = f"最新の{category}ニュースについて、重要なトピックを3つ程度、簡潔に要約して教えてください。"
        elif query:
            prompt = f"{query}に関する最新のニュースについて、重要なトピックを3つ程度、簡潔に要約して教えてください。"
        else:
            prompt = "現在の主要なニュースについて、重要なトピックを3つ程度、簡潔に要約して教えてください。"
        
        # APIリクエストの構築
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "pplx-7b-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "あなたは日下家の執事として、ニュースを簡潔に要約して伝える役割を担っています。" \
                             "常に丁寧な言葉遣いを心がけ、重要な情報を分かりやすく伝えてください。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        # APIリクエストの送信
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.text
            
    except Exception as e:
        return str(e)

def format_news(news_data: str, category: str = "", query: str = "") -> str:
    """
    ニュース情報を整形する
    
    Args:
        news_data (str): ニュース情報のJSON文字列
        category (str): ニュースカテゴリー（オプション）
        query (str): 検索クエリ（オプション）
    
    Returns:
        str: 整形されたニュース情報
    """
    try:
        data = json.loads(news_data)
        
        # レスポンスの整形
        if category:
            news_intro = f"{category}に関する最新のニュースをお知らせいたします：\n\n"
        elif query:
            news_intro = f"{query}に関する最新のニュースをお知らせいたします：\n\n"
        else:
            news_intro = "本日の主要なニュースをお知らせいたします：\n\n"
        
        news_content = data['choices'][0]['message']['content']
        return news_intro + news_content
        
    except Exception as e:
        return f"ニュース情報の整形中にエラーが発生いたしました：{str(e)}"

class NewsAgent(BaseAgent):
    """Agent for handling news information using Perplexity API"""
    
    def __init__(self):
        instructions = """
        あなたは日下家の執事として、ニュース情報を提供する役割を担っています。
        Perplexity APIを使用してニュース情報を取得し、丁寧な言葉遣いで情報を提供してください。
        
        以下の関数が利用可能です：
        - get_news(category: str = "", query: str = "") -> str
          指定されたカテゴリーやクエリに基づいてニュース情報を取得します。
        
        - format_news(news_data: str, category: str = "", query: str = "") -> str
          ニュース情報を人間が読みやすい形式に整形します。
        """
        
        functions = [
            get_news,
            format_news
        ]
        
        super().__init__(
            name="NewsAgent",
            instructions=instructions,
            functions=functions
        )

    def _determine_category(self, query: str) -> str:
        """
        クエリからニュースカテゴリーを判定する
        
        Args:
            query (str): ユーザーからの問い合わせ
            
        Returns:
            str: 判定されたカテゴリー
        """
        categories = {
            "ビジネス": ["経済", "企業", "ビジネス", "株価", "市場"],
            "政治": ["政治", "国会", "選挙", "首相", "大臣"],
            "スポーツ": ["スポーツ", "野球", "サッカー", "テニス", "オリンピック"],
            "科学技術": ["科学", "技術", "IT", "AI", "研究"],
            "エンタメ": ["芸能", "映画", "音楽", "エンタメ", "芸術"]
        }
        
        query_lower = query.lower()
        for category, keywords in categories.items():
            if any(keyword in query_lower for keyword in keywords):
                return category
        return ""

    def _extract_query(self, query: str) -> str:
        """
        問い合わせから検索キーワードを抽出する
        
        Args:
            query (str): ユーザーからの問い合わせ
            
        Returns:
            str: 抽出されたキーワード
        """
        # "最新のニュース"などの一般的なクエリの場合は空文字を返す
        if "最新" in query and "ニュース" in query:
            return ""
            
        # "について"や"の"などの前の部分を抽出
        for stop_word in ["について", "の", "を", "は", "が"]:
            if stop_word in query:
                return query.split(stop_word)[0].strip()
        return ""

    async def process(self, query: str) -> str:
        """
        ニュースに関する問い合わせを処理する
        
        Args:
            query (str): ユーザーからの問い合わせ
            
        Returns:
            str: ニュース情報のレスポンス
        """
        try:
            category = self._determine_category(query)
            search_query = self._extract_query(query)
            
            news_data = await get_news(category=category, query=search_query)
            return format_news(news_data, category=category, query=search_query)
            
        except Exception as e:
            return f"申し訳ございません。ニュース情報の取得中にエラーが発生いたしました：{str(e)}"
