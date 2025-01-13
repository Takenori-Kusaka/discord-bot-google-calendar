from litellm import completion
import os
from dotenv import load_dotenv
import logging
from typing import Dict, Any
from datetime import datetime


class LLMClient:
    def __init__(self, model_name: str):
        # ログの設定
        self._setup_logging()

        # 環境変数の読み込み
        load_dotenv()
        self.model_name = model_name
        self._setup_api_key()

        self.logger.info(f"LLMClient initialized with model: {model_name}")

    def _setup_logging(self):
        """ログ設定の初期化"""
        self.logger = logging.getLogger("LLMClient")
        self.logger.setLevel(logging.INFO)

        # ファイルハンドラーの設定
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        fh = logging.FileHandler(
            f'{log_dir}/llm_{datetime.now().strftime("%Y%m%d")}.log'
        )

        # コンソールハンドラーの設定
        ch = logging.StreamHandler()

        # フォーマットの設定
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def _setup_api_key(self):
        """API keyの設定と検証"""
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            self.logger.error("ANTHROPIC_API_KEY is not set")
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        os.environ["ANTHROPIC_API_KEY"] = self.api_key

    def send_message(self, content: str) -> Dict[str, Any]:
        """メッセージを送信し、レスポンスを返す"""
        try:
            self.logger.info(f"Sending message: {content[:50]}...")

            response = completion(
                model=self.model_name, messages=[{"content": content, "role": "user"}]
            )

            self.logger.info("Message sent successfully")
            self.logger.debug(f"Full response: {response}")

            return {
                "success": True,
                "response": response,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error sending message: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }


def main():
    try:
        # クライアントの初期化
        client = LLMClient("anthropic/claude-3-sonnet-20240229")

        # メッセージの送信
        result = client.send_message("Hello, how are you?")

        if result["success"]:
            print(f"Response received: {result['response']}")
        else:
            print(f"Error occurred: {result['error']}")

    except Exception as e:
        logging.error(f"Application error: {str(e)}")


if __name__ == "__main__":
    main()
