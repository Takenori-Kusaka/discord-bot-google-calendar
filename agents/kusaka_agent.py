from typing import Dict, Any
from .base_agent import BaseAgent


def get_kusaka_info(category: str = "") -> str:
    """
    日下家に関する情報を取得する（モック実装）

    Args:
        category (str): 情報カテゴリー（オプション）

    Returns:
        str: 日下家の情報
    """
    mock_data = {
        "家族構成": {
            "title": "日下家の家族構成",
            "content": "日下家の家族構成に関する情報です（モックデータ）。",
        },
        "歴史": {
            "title": "日下家の歴史",
            "content": "日下家の歴史に関する情報です（モックデータ）。",
        },
        "伝統": {
            "title": "日下家の伝統",
            "content": "日下家の伝統に関する情報です（モックデータ）。",
        },
        "事業": {
            "title": "日下家の事業",
            "content": "日下家の事業に関する情報です（モックデータ）。",
        },
    }

    if category and category in mock_data:
        return str(mock_data[category])
    return str(mock_data)


def format_kusaka_info(info_data: str) -> str:
    """
    日下家の情報を整形する

    Args:
        info_data (str): 情報のJSON文字列

    Returns:
        str: 整形された情報
    """
    try:
        data = eval(info_data)
        response = ""

        if isinstance(data, dict):
            if "title" in data:  # 単一カテゴリーの情報
                response = f"【{data['title']}】\n{data['content']}"
            else:  # 全カテゴリーの情報
                response = "日下家に関する情報をお知らせいたします：\n\n"
                for info in data.values():
                    response += f"【{info['title']}】\n{info['content']}\n\n"

        return response

    except Exception as e:
        return f"情報の整形中にエラーが発生いたしました：{str(e)}"


class KusakaAgent(BaseAgent):
    """Agent for handling Kusaka family information (Mock implementation)"""

    def __init__(self):
        instructions = """
        あなたは日下家の執事として、日下家に関する情報を提供する役割を担っています。
        現在はモック実装ですが、将来的にはMeilisearchを使用して情報を提供する予定です。
        常に丁寧な言葉遣いで情報を提供してください。
        
        以下の関数が利用可能です：
        - get_kusaka_info(category: str = "") -> str
          日下家に関する情報を取得します。カテゴリーを指定すると、特定の情報を取得できます。
        
        - format_kusaka_info(info_data: str) -> str
          取得した情報を人間が読みやすい形式に整形します。
        """

        functions = [get_kusaka_info, format_kusaka_info]

        super().__init__(
            name="KusakaAgent", instructions=instructions, functions=functions
        )

    def get_kusaka_info(self, category: str = "") -> str:
        """日下家に関する情報を取得する"""
        return get_kusaka_info(category)

    def format_kusaka_info(self, info_data: str) -> str:
        """日下家の情報を整形する"""
        return format_kusaka_info(info_data)

    async def process(self, query: str) -> str:
        """
        日下家に関する問い合わせを処理する

        Args:
            query (str): ユーザーからの問い合わせ

        Returns:
            str: 日下家の情報のレスポンス
        """
        try:
            # カテゴリーの判定
            categories = ["家族構成", "歴史", "伝統", "事業"]
            category = ""
            for c in categories:
                if c in query:
                    category = c
                    break

            # 情報の取得と整形
            info_data = self.get_kusaka_info(category)
            return self.format_kusaka_info(info_data)

        except Exception as e:
            return (
                f"申し訳ございません。情報の取得中にエラーが発生いたしました：{str(e)}"
            )
