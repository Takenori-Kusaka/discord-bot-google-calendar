from typing import Dict, Any, List
from .base_agent import BaseAgent
import json


class DisambiguationError(Exception):
    """Wikipediaの曖昧さ回避ページを示す例外"""

    def __init__(self, title: str, options: List[str]):
        self.title = title
        self.options = options
        super().__init__(f"'{title}' は曖昧さ回避ページです。オプション: {options}")


class PageError(Exception):
    """Wikipediaページが存在しないことを示す例外"""

    def __init__(self, title: str):
        self.title = title
        super().__init__(f"ページ '{title}' は存在しません。")


def search_wikipedia(query: str, num_results: int = 3) -> str:
    """
    Wikipediaで検索を実行する（モック実装）

    Args:
        query (str): 検索クエリ
        num_results (int): 取得する結果の数

    Returns:
        str: 検索結果のリスト
    """
    try:
        # モック実装
        results = ["テスト駅", "テスト (プログラミング)", "テスト理論"]
        return json.dumps(results[:num_results])
    except Exception as e:
        return str(e)


def get_wikipedia_content(title: str) -> str:
    """
    指定されたタイトルのWikipediaページの内容を取得する（モック実装）

    Args:
        title (str): 記事のタイトル

    Returns:
        str: ページの内容（要約）とURL
    """
    try:
        if title == "テスト駅":
            return json.dumps(
                {
                    "summary": "テスト駅に関する要約文です。",
                    "url": "https://ja.wikipedia.org/wiki/テスト駅",
                }
            )
        elif title == "存在しないページ":
            return json.dumps(
                {"error": True, "message": f"ページ '{title}' は存在しません。"}
            )
        elif title == "テスト":
            return json.dumps(
                {
                    "error": True,
                    "message": "'テスト' は曖昧さ回避ページです。",
                    "options": ["テスト (評価)", "テスト (工学)", "テスト (心理学)"],
                }
            )
        else:
            return json.dumps(
                {
                    "summary": f"{title}に関する要約文です。",
                    "url": f"https://ja.wikipedia.org/wiki/{title}",
                }
            )
    except (DisambiguationError, PageError) as e:
        return json.dumps({"error": True, "message": str(e)})
    except Exception as e:
        return str(e)


def format_wikipedia_info(search_data: str, content_data: str = None) -> str:
    """
    Wikipedia情報を整形する

    Args:
        search_data (str): 検索結果のリスト
        content_data (str): ページ内容のJSON文字列（オプション）

    Returns:
        str: 整形された情報
    """
    try:
        # JSON文字列をPythonオブジェクトに変換
        search_results = json.loads(search_data)

        if content_data:
            content = json.loads(content_data)

            if "error" in content:
                if "options" in content:
                    return "複数の意味が見つかりました。以下の候補から具体的にお申し付けください：\n\n" + "\n".join(
                        f"- {option}" for option in content["options"]
                    )
                return content["message"]

            response = f"以下の情報が見つかりました：\n\n{content['summary']}\n\n"
            response += f"詳細はこちらをご覧ください：\n{content['url']}"

            if len(search_results) > 1:
                response += "\n\n関連する項目：\n"
                for result in search_results[1:]:
                    response += f"- {result}\n"

            return response

        return "以下の項目が見つかりました：\n" + "\n".join(
            f"- {result}" for result in search_results
        )

    except Exception as e:
        return f"情報の整形中にエラーが発生いたしました：{str(e)}"


class WikipediaAgent(BaseAgent):
    """Agent for handling general information using Wikipedia API"""

    def __init__(self):
        instructions = """
        あなたは日下家の執事として、一般的な情報を提供する役割を担っています。
        Wikipedia APIを使用して情報を収集し、丁寧な言葉遣いで提供してください。
        
        以下の関数が利用可能です：
        - search_wikipedia(query: str, num_results: int = 3) -> str
          Wikipediaで検索を実行し、関連する記事のリストを取得します。
        
        - get_wikipedia_content(title: str) -> str
          指定されたタイトルのWikipediaページの内容を取得します。
        
        - format_wikipedia_info(search_data: str, content_data: str = None) -> str
          Wikipedia情報を人間が読みやすい形式に整形します。
        """

        functions = [search_wikipedia, get_wikipedia_content, format_wikipedia_info]

        super().__init__(
            name="WikipediaAgent", instructions=instructions, functions=functions
        )

    def format_wikipedia_info(self, search_data: str, content_data: str = None) -> str:
        """Wikipedia情報を整形する"""
        return format_wikipedia_info(search_data, content_data)

    async def process(self, query: str) -> str:
        """
        Wikipedia情報に関する問い合わせを処理する

        Args:
            query (str): ユーザーからの問い合わせ

        Returns:
            str: Wikipedia情報のレスポンス
        """
        try:
            # まず検索を実行
            search_results = search_wikipedia(query)

            # 検索結果がある場合、最初の結果の詳細を取得
            if search_results and search_results != "[]":
                results = json.loads(search_results)
                if results:
                    content = get_wikipedia_content(results[0])
                    return self.format_wikipedia_info(search_results, content)

            return self.format_wikipedia_info(search_results)

        except Exception as e:
            return (
                f"申し訳ございません。情報の取得中にエラーが発生いたしました：{str(e)}"
            )
