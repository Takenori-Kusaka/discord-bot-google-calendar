# デプロイガイド

執事「黒田」をNUCサーバーにデプロイする手順です。

## 前提条件

- SSH接続: `kusaka-server@192.168.68.79`
- Docker/Docker Compose インストール済み
- プロジェクトディレクトリ: `~/butler-kuroda/`

## デプロイ方法

### 方法1: 手動デプロイ（推奨）

```bash
# プロジェクトルートで実行
./scripts/deploy.sh
```

### 方法2: 個別コマンド

#### 1. ファイル転送

```bash
scp -r src config docker credentials pyproject.toml poetry.lock .env \
    kusaka-server@192.168.68.79:~/butler-kuroda/
```

#### 2. Dockerビルド・起動

```bash
ssh kusaka-server@192.168.68.79 "cd butler-kuroda/docker && docker-compose up -d --build"
```

## 運用コマンド

### ステータス確認

```bash
ssh kusaka-server@192.168.68.79 "docker ps | grep butler-kuroda"
```

### ログ確認

```bash
# 最新30行
ssh kusaka-server@192.168.68.79 "docker logs butler-kuroda --tail 30"

# リアルタイム
ssh kusaka-server@192.168.68.79 "docker logs butler-kuroda -f"
```

### 再起動

```bash
ssh kusaka-server@192.168.68.79 "cd butler-kuroda/docker && docker-compose restart"
```

### 停止

```bash
ssh kusaka-server@192.168.68.79 "cd butler-kuroda/docker && docker-compose down"
```

### 完全削除（イメージ含む）

```bash
ssh kusaka-server@192.168.68.79 "cd butler-kuroda/docker && docker-compose down --rmi all -v"
```

## トラブルシューティング

### Docker認証エラー

```
error getting credentials - err: exit status 1
```

**対処**: イメージを先に手動でpull

```bash
ssh kusaka-server@192.168.68.79 "docker pull python:3.11-slim"
```

### コンテナが起動しない

```bash
# 詳細ログ確認
ssh kusaka-server@192.168.68.79 "docker logs butler-kuroda"

# コンテナ状態確認
ssh kusaka-server@192.168.68.79 "docker inspect butler-kuroda"
```

### ヘルスチェック失敗

```bash
# ヘルスチェック状態確認
ssh kusaka-server@192.168.68.79 "docker inspect --format='{{.State.Health.Status}}' butler-kuroda"
```

## 環境変数

デプロイ時に必要な環境変数（`.env`）:

| 変数名 | 説明 |
|--------|------|
| `DISCORD_BOT_TOKEN` | Discord Botトークン |
| `DISCORD_GUILD_ID` | サーバーID |
| `DISCORD_OWNER_ID` | オーナーのユーザーID |
| `GOOGLE_CALENDAR_ID` | カレンダーID |
| `GOOGLE_CREDENTIALS_PATH` | 認証情報パス |
| `ANTHROPIC_API_KEY` | Claude APIキー |
| `CLAUDE_MODEL` | 使用モデル |
| `MORNING_NOTIFICATION_HOUR` | 通知時刻（時） |
| `MORNING_NOTIFICATION_MINUTE` | 通知時刻（分） |
| `TIMEZONE` | タイムゾーン |

## サーバー情報

| 項目 | 値 |
|------|-----|
| **ホスト** | `kusaka-server@192.168.68.79` |
| **OS** | Windows (Docker Desktop) |
| **プロジェクトパス** | `C:\Users\kusaka-server\butler-kuroda\` |
| **コンテナ名** | `butler-kuroda` |

---

*最終更新: 2026-01-16*
