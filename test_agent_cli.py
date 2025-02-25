import os
import asyncio
import logging
from typing import List
from dotenv import load_dotenv
from anthropic import Anthropic
from agents.types import AgentResponse, OrchestratorConfiguration
from agents.calendar_agent import CalendarAgent

# ロガーの設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# HTTPXのデバッグログを無効化（ノイズ削減）
logging.getLogger("httpx").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.INFO)

class Agent:
    """基本エージェントクラス"""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.tools = []
        self.logger = logging.getLogger(f"Agent.{name}")

    async def process(self, input_text: str) -> AgentResponse:
        """入力テキストを処理"""
        raise NotImplementedError

class AnthropicAgent(Agent):
    """Anthropicのモデルを使用するエージェント"""
    def __init__(self, name: str, description: str, system_prompt: str):
        super().__init__(name, description)
        self.system_prompt = system_prompt
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.logger.debug(f"Initializing Anthropic client with API key: {api_key[:6]}...")
        self.client = Anthropic(api_key=api_key)

    async def process(self, input_text: str) -> AgentResponse:
        """入力テキストを処理"""
        try:
            self.logger.debug(f"Processing input: {input_text}")
            self.logger.debug(f"Using system prompt: {self.system_prompt}")
            
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1024,
                system=self.system_prompt,
                messages=[{"role": "user", "content": input_text}]
            )
            
            response_text = message.content[0].text if message.content else "応答がありません。"
            self.logger.debug(f"Received response: {response_text}")
            return AgentResponse(
                agent_name=self.name,
                response=response_text
            )
        except Exception as e:
            self.logger.error(f"Error processing input: {str(e)}", exc_info=True)
            return AgentResponse(
                agent_name=self.name,
                response=f"エラーが発生しました: {str(e)}"
            )

class ButlerAgent(AnthropicAgent):
    """執事として振る舞うエージェント"""
    def __init__(self):
        super().__init__(
            name="butler",
            description="日下家の執事として振る舞うエージェント",
            system_prompt="""あなたは日下家の執事、瀬川 忠義として振る舞います。
            ユーザーからの要望に応じて、適切な機能を使用して情報を提供してください。
            常に丁寧な言葉遣いを心がけ、執事らしい応対を行ってください。"""
        )
        self.logger = logging.getLogger("Agent.Butler")

async def main():
    """メイン処理"""
    logger.info("Starting application")
    
    # 環境変数の読み込み
    load_dotenv()
    logger.debug("Environment variables loaded")
    
    # Google Service Account JSONの確認
    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        logger.debug("GOOGLE_SERVICE_ACCOUNT_JSON length: %d", len(service_account_json))
        logger.debug("GOOGLE_SERVICE_ACCOUNT_JSON first 100 chars: %s", service_account_json[:100])
    else:
        logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON is not set")
    
    # エージェントの初期化
    logger.info("Initializing agents")
    butler_agent = ButlerAgent()
    calendar_agent = CalendarAgent(test_mode=False)  # 本番モードで実行
    
    # オーケストレーター設定
    config = OrchestratorConfiguration(
        agents=[butler_agent, calendar_agent],
        default_agent_name=butler_agent.name
    )
    logger.debug("Orchestrator configuration created")
    
    print("\n=== テストを開始します。終了するには 'exit' と入力してください。 ===\n")
    
    while True:
        # ユーザー入力の受け取り
        user_input = input("\nユーザー入力を入力してください: ")
        logger.debug(f"Received user input: {user_input}")
        
        if user_input.lower() == 'exit':
            logger.info("Received exit command")
            break
        
        try:
            # デフォルトエージェント（執事）で処理
            logger.debug("Processing with butler agent")
            result = await butler_agent.process(user_input)
            print("\n[執事の応答]")
            print(result.response)
            
            # カレンダー関連の内容の場合、カレンダーエージェントで処理
            if any(word in user_input for word in ["予定", "スケジュール", "打ち合わせ", "ミーティング"]):
                logger.debug("Calendar-related input detected, processing with calendar agent")
                calendar_result = await calendar_agent.process(user_input)
                print("\n[カレンダーエージェントの応答]")
                print(calendar_result.response)
            
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}", exc_info=True)
            print(f"\nエラーが発生しました: {str(e)}")
    
    logger.info("Application shutting down")

if __name__ == "__main__":
    asyncio.run(main())