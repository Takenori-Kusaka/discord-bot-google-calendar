import os
import json
import logging
import discord
from discord.ext import commands
from typing import List, Optional, Dict
from datetime import datetime
from zoneinfo import ZoneInfo
from anthropic import Anthropic
from agents.types import AgentResponse
from agents.calendar_agent import CalendarAgent
from agents.weather_agent import WeatherAgent

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class KusakaButler(commands.Bot):
    """日下家の執事として動作するDiscord Bot"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        
        # エージェントの初期化
        api_key = os.getenv("ANTHROPIC_API_KEY")
        logger.debug(f"Initializing Anthropic client with API key: {api_key[:6]}...")
        self.client = Anthropic(api_key=api_key)
        self.calendar_agent = CalendarAgent(test_mode=False)
        self.weather_agent = WeatherAgent()
        self.timezone = ZoneInfo("Asia/Tokyo")
        
        # 執事のシステムプロンプト
        self.system_prompt = """あなたは日下家の執事、瀬川 忠義として振る舞います。
ユーザーからの要望に応じて、適切な機能を使用して情報を提供してください。
常に丁寧な言葉遣いを心がけ、執事らしい応対を行ってください。"""
        
        logger.info("KusakaButler initialized")
    
    async def setup_hook(self):
        """Bot起動時の初期設定"""
        logger.info("瀬川 忠義が起動いたしました。")
    
    async def on_ready(self):
        """Bot準備完了時の処理"""
        logger.info(f"{self.user}として正常にログインいたしました。")
    
    async def on_message(self, message: discord.Message):
        """メッセージ受信時の処理"""
        # 自分自身のメッセージは無視
        if message.author == self.user:
            return
        
        # コマンド処理
        await self.process_commands(message)
        
        # メンションされた場合のみ応答
        if self.user not in message.mentions:
            return
        
        # メンションを除去してメッセージ内容を取得
        content = message.content.replace(f'<@{self.user.id}>', '').strip()
        if not content:
            await message.channel.send("ご用件をお申し付けください。")
            return
        
        try:
            # 執事としての応答を生成
            butler_response = await self._get_butler_response(content)
            await message.channel.send(butler_response)
            
            # カレンダー関連の内容の場合
            if any(word in content for word in ["予定", "スケジュール", "打ち合わせ", "ミーティング"]):
                logger.debug("Calendar-related input detected, processing with calendar agent")
                calendar_result = await self.calendar_agent.process(content)
                await message.channel.send(calendar_result.response)
            
            # 天気関連の内容の場合
            elif any(word in content for word in ["天気", "気温", "雨", "晴れ", "傘"]):
                logger.debug("Weather-related input detected, processing with weather agent")
                weather_result = await self.weather_agent.process(content)
                await message.channel.send(weather_result.response)
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            await message.channel.send(f"申し訳ございません。エラーが発生いたしました。\n{str(e)}")
    
    async def _get_butler_response(self, content: str) -> str:
        """執事としての応答を生成"""
        try:
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1024,
                system=self.system_prompt,
                messages=[{"role": "user", "content": content}]
            )
            return message.content[0].text if message.content else "申し訳ございません。応答を生成できませんでした。"
            
        except Exception as e:
            logger.error(f"Error generating butler response: {str(e)}", exc_info=True)
            return f"申し訳ございません。応答の生成中にエラーが発生いたしました。"

def main():
    """Botのメイン処理"""
    # 環境変数の読み込み
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        raise ValueError("DISCORD_TOKEN environment variable is required")
    
    # Botの起動
    bot = KusakaButler()
    bot.run(token)

if __name__ == "__main__":
    main()
