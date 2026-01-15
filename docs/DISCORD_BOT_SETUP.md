# Discord Bot 設定ガイド

## Bot基本情報

### アプリケーション名
```
黒田 - 日下家の執事
```

### 説明文（Description）
```
日下家に仕える家庭内執事AIアシスタント「黒田」でございます。
毎朝のご予定のお知らせ、地域イベント情報のご提案、
お問い合わせへの対応など、ご家族の生活をサポートいたします。
```

### タグ（Tags）
- `家庭用`
- `スケジュール管理`
- `AIアシスタント`

---

## Discord Developer Portal 設定

### 1. General Information
https://discord.com/developers/applications/{APP_ID}/information

| 項目 | 設定値 |
|------|--------|
| **NAME** | 黒田 - 日下家の執事 |
| **DESCRIPTION** | 上記の説明文 |
| **ICON** | 執事アイコン（下記プロンプト参照） |

### 2. Bot設定
https://discord.com/developers/applications/{APP_ID}/bot

| 項目 | 設定値 |
|------|--------|
| **USERNAME** | 黒田 |
| **PUBLIC BOT** | OFF（プライベート用） |
| **REQUIRES OAUTH2 CODE GRANT** | OFF |

#### Privileged Gateway Intents
| Intent | 設定 | 用途 |
|--------|------|------|
| **PRESENCE INTENT** | OFF | 不要 |
| **SERVER MEMBERS INTENT** | OFF | 不要 |
| **MESSAGE CONTENT INTENT** | ✅ ON | メッセージ内容の読み取り |

### 3. OAuth2設定
https://discord.com/developers/applications/{APP_ID}/oauth2

#### URL Generator
**Scopes:**
- ✅ `bot`
- ✅ `applications.commands`

**Bot Permissions:**
- ✅ Send Messages
- ✅ Send Messages in Threads
- ✅ Embed Links
- ✅ Read Message History
- ✅ View Channels
- ✅ Use External Emojis（任意）

**生成されるPermission Integer:** `274877991936`

#### 招待URL例
```
https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&permissions=274877991936&scope=bot%20applications.commands
```

---

## アイコン生成プロンプト

### Google Gemini (Nano/Banana) 用プロンプト

```
A dignified elderly Japanese butler icon for a Discord bot.

Style: Clean, professional, circular avatar suitable for Discord
Character: A distinguished elderly Japanese man (60s) in formal butler attire
- Silver/gray hair, neatly combed
- Kind but professional expression
- Wearing a classic black tailcoat with white shirt
- Small bow tie
- Clean-shaven or subtle mustache

Colors:
- Dark navy/black for the suit
- White accents
- Warm skin tones
- Soft background (cream or light gray)

Composition:
- Head and shoulders portrait
- Centered, looking slightly to the side
- Subtle smile suggesting reliability and warmth
- High contrast for visibility at small sizes

Do NOT include: text, logos, busy backgrounds, bright colors
```

### 代替プロンプト（シンプル版）
```
Professional Japanese butler avatar for Discord bot.
Elderly gentleman, silver hair, black tailcoat, white shirt, bow tie.
Dignified and warm expression. Clean circular icon design.
No text, simple background.
```

---

## サーバー設定確認

### 日下家サーバー

**Guild ID:** `1325036694524792874`

### チャンネル確認

| チャンネル名 | 用途 |
|-------------|------|
| #予定 | 朝の予定通知 |
| #地域のこと | 地域イベント情報 |
| #家のこと | 家族関連通知 |
| #子供のこと | 子供関連情報 |
| #news | ニュース |

### Botの権限確認

サーバー設定 → ロール → 黒田（Bot）
- ✅ メッセージを送信
- ✅ メッセージ履歴を読む
- ✅ チャンネルを見る

---

## 動作確認チェックリスト

### Discord Developer Portal
- [ ] Bot名を「黒田」に設定
- [ ] 説明文を設定
- [ ] アイコンをアップロード
- [ ] MESSAGE CONTENT INTENTを有効化
- [ ] PUBLIC BOTをOFF

### サーバー側
- [ ] Botがサーバーに参加している
- [ ] #予定チャンネルへの送信権限あり
- [ ] #地域のことチャンネルへの送信権限あり

### 環境設定
- [ ] DISCORD_BOT_TOKEN設定済み
- [ ] DISCORD_GUILD_ID設定済み
- [ ] DISCORD_OWNER_ID設定済み

---

*最終更新: 2026-01-15*
