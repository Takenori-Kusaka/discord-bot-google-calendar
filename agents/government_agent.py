import requests
from typing import Dict, Any
from bs4 import BeautifulSoup
import asyncio
from .base_agent import BaseAgent


def crawl_government_website(url: str, query: str = "") -> str:
    """
    政府・自治体のWebサイトをクロールする

    Args:
        url (str): クロール対象のURL
        query (str): 検索クエリ（オプション）

    Returns:
        str: 抽出された情報
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # 検索ページのURLを構築
        search_url = f"{url}/search" if query else url
        params = {"q": query} if query else None

        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # 検索結果の抽出
        results = []
        search_results = soup.find_all(
            ["h2", "h3", "a"], class_=["title", "result-title"]
        )[:3]

        if not search_results:
            return "関連する情報は見つかりませんでした。"

        for result in search_results:
            title = result.text.strip()
            link = result.get("href", "")
            if link and not link.startswith("http"):
                link = url + link
            results.append(f"- {title}\n  {link}")

        return "\n".join(results)

    except Exception as e:
        return str(e)


def format_government_info(source: str, info: str) -> str:
    """
    政府・自治体の情報を整形する

    Args:
        source (str): 情報源（機関名）
        info (str): クロール結果

    Returns:
        str: 整形された情報
    """
    return f"【{source}】\n{info}\n"


class GovernmentAgent(BaseAgent):
    """Agent for handling government and local authority information"""

    def __init__(self):
        self.sources = {
            "総務省": "https://www.soumu.go.jp",
            "文部科学省": "https://www.mext.go.jp",
            "農林水産省": "https://www.maff.go.jp",
            "デジタル庁": "https://www.digital.go.jp",
            "子ども家庭庁": "https://www.cfa.go.jp",
            "内閣府": "https://www.cao.go.jp",
            "国土交通省": "https://www.mlit.go.jp",
            "財務省": "https://www.mof.go.jp",
            "京都府": "https://www.pref.kyoto.jp",
            "木津川市": "https://www.city.kizugawa.lg.jp",
        }

        instructions = """
        あなたは日下家の執事として、政府や自治体の情報を提供する役割を担っています。
        各機関のWebサイトから情報を収集し、丁寧な言葉遣いで提供してください。
        
        以下の関数が利用可能です：
        - crawl_government_website(url: str, query: str = "") -> str
          政府・自治体のWebサイトから情報を収集します。
        
        - format_government_info(source: str, info: str) -> str
          収集した情報を人間が読みやすい形式に整形します。
        
        対応している機関：
        - 総務省
        - 文部科学省
        - 農林水産省
        - デジタル庁
        - 子ども家庭庁
        - 内閣府
        - 国土交通省
        - 財務省
        - 京都府
        - 木津川市
        """

        functions = [crawl_government_website, format_government_info]

        super().__init__(
            name="GovernmentAgent", instructions=instructions, functions=functions
        )

    def format_government_info(self, source: str, info: str) -> str:
        """政府・自治体の情報を整形する"""
        return format_government_info(source, info)

    async def process(self, query: str) -> str:
        """
        政府・自治体に関する問い合わせを処理する

        Args:
            query (str): ユーザーからの問い合わせ

        Returns:
            str: 政府・自治体の情報のレスポンス
        """
        try:
            response = "政府・自治体からの情報をお知らせいたします：\n\n"
            tasks = []

            # 問い合わせ内容から対象機関を特定
            target_sources = {}
            for source, url in self.sources.items():
                if source in query:
                    target_sources[source] = url

            # 特定の機関が指定されていない場合は、文部科学省をデフォルトとする
            if not target_sources:
                target_sources = {"文部科学省": self.sources["文部科学省"]}

            # 各機関からの情報収集
            for source, url in target_sources.items():
                info = crawl_government_website(url, query)
                response += self.format_government_info(source, info)

            return response

        except Exception as e:
            return (
                f"申し訳ございません。情報の取得中にエラーが発生いたしました：{str(e)}"
            )
