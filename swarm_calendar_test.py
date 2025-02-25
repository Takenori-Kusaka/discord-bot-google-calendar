import os
import openai
from datetime import datetime
import asyncio
import json
import logging
from swarm import Swarm
from agents.calendar_agent import CalendarAgent
from dotenv import load_dotenv

# ロガーの設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ファイルハンドラの設定
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)
fh = logging.FileHandler(os.path.join(log_dir, 'calendar_test.log'))
fh.setLevel(logging.DEBUG)

# コンソールハンドラの設定
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# フォーマッタの設定
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# ハンドラをロガーに追加
logger.addHandler(fh)
logger.addHandler(ch)

load_dotenv()

# OpenAIクライアントを初期化します
openai_client = openai.OpenAI(
    api_key=os.getenv("LITE_LLM_API_KEY"),
    base_url=os.getenv("LITE_LLM_ENDPOINT_URL"),
)

async def process_calendar_request(text: str) -> str:
    """カレンダーリクエストを処理する"""
    try:
        logger.info("Starting calendar request processing: %s", text)
        
        # Swarmの初期化（OpenAIクライアントを使用）
        client = Swarm(openai_client)
        
        # CalendarAgentのインスタンス化
        calendar_agent = CalendarAgent()
        
        # メッセージの作成
        messages = [{"role": "user", "content": text}]
        
        # SwarmAgentを取得
        swarm_agent = calendar_agent.get_agent()
        logger.debug("Swarm agent retrieved: %s", swarm_agent.name)
        
        # Swarmを介してメッセージを処理
        logger.debug("Calling Swarm with message: %s", messages)
        response = client.run(agent=swarm_agent, messages=messages)
        response_text = response.messages[-1]["content"]
        logger.debug("Swarm response received: %s", response_text)
        
        # カレンダー処理の実行
        logger.info("Processing calendar event")
        result = await calendar_agent.process(text)
        logger.info("Calendar processing completed: %s", result)
        
        return result
        
    except Exception as e:
        logger.error("Error in calendar request processing", exc_info=True)
        return f"エラーが発生しました: {str(e)}"

# テストケース
test_cases = [
    "明日の10時から11時まで会議を設定して",
    "明後日の午後3時から2時間打ち合わせ",
    "来週月曜日の朝9時から10時までミーティング",
]

# テストの実行
async def run_test(test_input: str):
    logger.info("Running test case: %s", test_input)
    try:
        result = await process_calendar_request(test_input)
        logger.info("Test result: %s", result)
        print(result)
    except Exception as e:
        logger.error("Test failed", exc_info=True)
        print(f"エラー: {str(e)}")

async def run_all_tests():
    logger.info("Starting test suite")
    for test_input in test_cases:
        await run_test(test_input)
    logger.info("Test suite completed")

if __name__ == "__main__":
    # 環境変数の確認
    if not os.getenv("LITE_LLM_API_KEY") or not os.getenv("LITE_LLM_ENDPOINT_URL"):
        logger.error("Required environment variables not set")
        print("Error: LITE_LLM_API_KEY or LITE_LLM_ENDPOINT_URL is not set in .env file")
        exit(1)
    
    logger.info("Starting calendar test application")
    # テストを実行
    asyncio.run(run_all_tests())