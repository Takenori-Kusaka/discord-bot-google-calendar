"""週次イベント通知の完全テスト（Discord送信含む）

実際のAPIを使用して、週次イベント通知を実行します。
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

async def main():
    print("=" * 60)
    print("週次イベント通知 完全テスト（Discord送信含む）")
    print(f"実行日時: {datetime.now(ZoneInfo('Asia/Tokyo'))}")
    print("=" * 60)
    
    # 設定を読み込み
    from src.config.settings import get_settings
    settings = get_settings()
    
    # 各クライアントを初期化
    from src.clients.event_search import EventSearchClient
    from src.clients.claude import ClaudeClient
    from src.clients.discord import DiscordClient
    
    event_search = EventSearchClient(
        google_api_key=settings.google_search_api_key,
        google_search_engine_id=settings.google_search_engine_id,
        perplexity_api_key=getattr(settings, 'perplexity_api_key', None),
        timezone=settings.timezone,
    )
    
    claude = ClaudeClient(
        api_key=settings.anthropic_api_key,
        model=settings.claude_model,
    )
    
    discord = DiscordClient(
        token=settings.discord_bot_token,
        guild_id=settings.discord_guild_id,
        owner_id=settings.discord_owner_id,
    )
    
    print(f"\n[Step 1] 地域イベントを検索中...")
    search_results = await event_search.search_events()
    print(f"  → 検索結果: {len(search_results)}件")
    
    print(f"\n[Step 2] 検索結果からイベント情報を抽出中...")
    events = await claude.extract_events_from_search(search_results)
    print(f"  → 抽出されたイベント: {len(events)}件")
    
    # フォールバック処理
    if not events and search_results:
        print(f"  → フォールバック: 検索結果からイベントを構築...")
        events = event_search.build_events_from_results(search_results)
        print(f"  → 構築されたイベント: {len(events)}件")
    
    if not events:
        print(f"  → 参考イベントを生成...")
        events = event_search.build_reference_events()
        print(f"  → 参考イベント: {len(events)}件")
    
    print(f"\n[Step 3] 家族向けおすすめメッセージを生成中...")
    message = await claude.generate_event_recommendation(
        events,
        butler_name="黒田",
    )
    
    # 参考リンクを追加
    reference_links = event_search.format_reference_links()
    if reference_links:
        message = message + reference_links
    
    print(f"\n" + "=" * 60)
    print("生成されたメッセージ:")
    print("=" * 60)
    print(message)
    print("=" * 60)
    
    print(f"\n[Step 4] Discordに送信中...")
    
    # Discord Botを起動して送信
    import discord as pycord
    
    class TestBot(pycord.Client):
        def __init__(self, message_to_send, channel_name):
            intents = pycord.Intents.default()
            super().__init__(intents=intents)
            self.message_to_send = message_to_send
            self.channel_name = channel_name
            self.sent = False
        
        async def on_ready(self):
            print(f"  → Bot logged in as {self.user}")
            
            guild = self.get_guild(settings.discord_guild_id)
            if not guild:
                print(f"  ❌ Guild not found: {settings.discord_guild_id}")
                await self.close()
                return
            
            # チャンネルを検索
            channel = None
            for ch in guild.text_channels:
                if ch.name == self.channel_name:
                    channel = ch
                    break
            
            if not channel:
                print(f"  ❌ Channel not found: {self.channel_name}")
                await self.close()
                return
            
            try:
                await channel.send(self.message_to_send)
                print(f"  ✅ メッセージを送信しました: #{self.channel_name}")
                self.sent = True
            except Exception as e:
                print(f"  ❌ 送信エラー: {e}")
            
            await self.close()
    
    bot = TestBot(message, settings.discord_channel_region)
    await bot.start(settings.discord_bot_token)
    
    print(f"\n[結果]")
    if bot.sent:
        print("  ✅ 週次イベント通知が正常に送信されました")
    else:
        print("  ❌ 送信に失敗しました")

if __name__ == "__main__":
    asyncio.run(main())
