# アーキテクチャ設計書

## システム概要

家庭内執事「黒田」は、スケジュールベースのタスク実行とDiscordインタラクションを提供するAIアシスタントです。

---

## システム構成図

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NUC Server (Docker)                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      Butler "Kuroda"                          │  │
│  │                                                               │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │  │
│  │  │  Scheduler  │───→│   Butler    │───→│  Discord    │      │  │
│  │  │ (APScheduler)│    │   Core      │    │   Client    │      │  │
│  │  └─────────────┘    └──────┬──────┘    └──────┬──────┘      │  │
│  │                            │                   │              │  │
│  │         ┌──────────────────┼───────────────────┘              │  │
│  │         │                  │                                  │  │
│  │         ▼                  ▼                                  │  │
│  │  ┌─────────────┐    ┌─────────────┐                          │  │
│  │  │  Claude     │    │  Config     │                          │  │
│  │  │  API Client │    │  Manager    │                          │  │
│  │  └─────────────┘    └─────────────┘                          │  │
│  │                                                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Claude    │      │   Google    │      │   Discord   │
│    API      │      │  Calendar   │      │    API      │
└─────────────┘      └─────────────┘      └─────────────┘
```

---

## コンポーネント設計

### 1. Butler Core（中核）

執事の中心ロジックを担当。

```python
class Butler:
    """執事「黒田」のコアクラス"""

    async def morning_notification(self):
        """朝の予定通知"""
        events = await self.calendar.get_today_events()
        important = await self.claude.filter_important_events(events)
        await self.discord.send_schedule(important)

    async def handle_message(self, message: str):
        """Discordメッセージ処理（Phase 3）"""
        pass
```

### 2. Scheduler（スケジューラ）

APSchedulerを使用した定期実行。

| ジョブ | スケジュール | 機能 |
|-------|-------------|------|
| `morning_notification` | 毎日 6:00 | 朝の予定通知 |
| `weekly_events` | 毎週金曜 18:00 | 地域イベント（Phase 2） |

### 3. Calendar Client（Google Calendar連携）

```python
class GoogleCalendarClient:
    """Google Calendar API クライアント"""

    async def get_today_events(self) -> List[Event]:
        """今日の予定を取得"""
        pass

    async def get_week_events(self) -> List[Event]:
        """今週の予定を取得"""
        pass
```

### 4. Claude Client（LLM連携）

```python
class ClaudeClient:
    """Claude API クライアント"""

    async def filter_important_events(
        self,
        events: List[Event],
        rules: FilterRules
    ) -> List[Event]:
        """重要な予定をフィルタリング"""
        pass

    async def generate_message(
        self,
        template: str,
        context: dict
    ) -> str:
        """執事口調のメッセージ生成"""
        pass
```

### 5. Discord Client（Discord連携）

```python
class DiscordClient:
    """Discord Bot クライアント"""

    async def send_to_channel(
        self,
        channel_name: str,
        message: str
    ):
        """チャンネルにメッセージ送信"""
        pass

    async def send_dm(self, user_id: str, message: str):
        """DMでエラー通知"""
        pass
```

### 6. Config Manager（設定管理）

```python
class ConfigManager:
    """設定管理"""

    def load_env(self) -> Config:
        """環境変数から設定読み込み"""
        pass

    def load_rules(self) -> FilterRules:
        """フィルタリングルール読み込み"""
        pass
```

---

## データフロー

### 朝の予定通知（MVP）

```
[06:00 Trigger]
      │
      ▼
┌─────────────────┐
│ Scheduler       │
│ triggers job    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Calendar Client │────→│ Google Calendar │
│ get_today_events│←────│ API             │
└────────┬────────┘     └─────────────────┘
         │
         │ List[Event]
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Claude Client   │────→│ Claude API      │
│ filter_events   │←────│                 │
└────────┬────────┘     └─────────────────┘
         │
         │ List[ImportantEvent]
         ▼
┌─────────────────┐
│ Claude Client   │
│ generate_message│
└────────┬────────┘
         │
         │ 執事口調メッセージ
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Discord Client  │────→│ Discord API     │
│ send_to_channel │     │ #予定           │
└─────────────────┘     └─────────────────┘
```

---

## ディレクトリ構造

```
discord-bot-google-calendar/
├── .github/
│   └── workflows/           # CI/CD
├── .work/                   # 作業用（git除外）
│   ├── notes/
│   ├── tickets/
│   └── temp/
├── docs/                    # ドキュメント
│   ├── personal/            # サブモジュール（家族情報）
│   ├── PROJECT.md
│   ├── REQUIREMENTS.md
│   ├── ARCHITECTURE.md
│   └── TECH_RESEARCH.md
├── src/                     # ソースコード（新規）
│   ├── __init__.py
│   ├── main.py              # エントリーポイント
│   ├── butler.py            # Butlerコアクラス
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── calendar.py      # Google Calendar
│   │   ├── claude.py        # Claude API
│   │   └── discord.py       # Discord Bot
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── jobs.py          # スケジュールジョブ
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py      # 設定管理
│   └── utils/
│       ├── __init__.py
│       └── logger.py        # ログ
├── config/                  # 設定ファイル（新規）
│   ├── ignore_rules.yml     # 通知しない予定
│   └── notify_rules.yml     # 必ず通知する予定
├── tests/                   # テスト
│   ├── __init__.py
│   ├── test_butler.py
│   ├── test_calendar.py
│   └── test_claude.py
├── docker/                  # Docker関連（新規）
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.template            # 環境変数テンプレート
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## 技術スタック詳細

### 言語・ランタイム

| 項目 | 選定 | 理由 |
|------|------|------|
| 言語 | Python 3.11+ | 既存コードベース、ライブラリ充実 |
| 非同期 | asyncio | Discord.py、aiohttp対応 |
| 型ヒント | typing, Pydantic | 型安全性、バリデーション |

### ライブラリ

| 用途 | ライブラリ | バージョン |
|------|-----------|-----------|
| Discord Bot | discord.py | 2.x |
| Google Calendar | google-api-python-client | 2.x |
| Claude API | anthropic | 最新 |
| スケジューラ | APScheduler | 3.x |
| HTTP | aiohttp | 3.x |
| 設定 | pydantic-settings | 2.x |
| ログ | structlog | 最新 |
| テスト | pytest, pytest-asyncio | 最新 |

### インフラ

| 項目 | 選定 | 理由 |
|------|------|------|
| コンテナ | Docker | 移植性、再現性 |
| オーケストレーション | docker-compose | シンプル、単一サーバー向け |
| プロセス管理 | Docker restart policy | 自動再起動 |

---

## Docker構成

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 依存関係インストール
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

# アプリケーションコピー
COPY src/ ./src/
COPY config/ ./config/

# 実行
CMD ["poetry", "run", "python", "-m", "src.main"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  butler:
    build: .
    container_name: butler-kuroda
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config:ro
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 環境変数

```bash
# .env.template

# Discord
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=your_guild_id
DISCORD_OWNER_ID=your_user_id

# Google Calendar
GOOGLE_CALENDAR_ID=ty.family.kusaka@gmail.com
GOOGLE_CREDENTIALS_PATH=/app/credentials/google.json

# Claude API
ANTHROPIC_API_KEY=your_anthropic_api_key
CLAUDE_MODEL=claude-sonnet-4-20250514

# Schedule
MORNING_NOTIFICATION_HOUR=6
MORNING_NOTIFICATION_MINUTE=0
TIMEZONE=Asia/Tokyo

# Logging
LOG_LEVEL=INFO
```

---

## セキュリティ考慮事項

1. **API キー管理**
   - 環境変数で管理（.envはgit除外）
   - Docker secretsも検討可能

2. **Google認証情報**
   - サービスアカウントJSON使用
   - ファイルはgit除外、Dockerボリュームでマウント

3. **個人情報**
   - personalリポジトリは非公開
   - ログに個人情報を出力しない

---

## エラーハンドリング

```python
class ButlerError(Exception):
    """執事エラー基底クラス"""
    pass

class CalendarError(ButlerError):
    """カレンダーAPI エラー"""
    pass

class ClaudeError(ButlerError):
    """Claude API エラー"""
    pass

class DiscordError(ButlerError):
    """Discord API エラー"""
    pass
```

### エラー通知フロー

```
[Error発生]
     │
     ▼
┌─────────────────┐
│ ログ出力        │
│ (structlog)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Discord DM送信  │
│ (旦那様へ)      │
└─────────────────┘
```

---

## 次のステップ

1. [ ] src/ディレクトリ構造を作成
2. [ ] 基本的なクラス骨格を実装
3. [ ] Docker環境をセットアップ
4. [ ] Google Calendar認証設定
5. [ ] Discord Bot設定
6. [ ] Claude APIテスト
7. [ ] 統合テスト

---

*最終更新: 2026-01-14*
