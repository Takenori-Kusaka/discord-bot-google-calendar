# デプロイガイド

執事「黒田」を kusaka-server（Windows + Docker Desktop）にデプロイする手順です。

## 全体像

```
ローカル (git commit → git push)
        │
        ▼
GitHub  main  ──── ソース・オブ・トゥルース ────┐
                                                 │ git pull --ff-only
                                                 ▼
kusaka-server  C:\Users\kusaka-server\butler-kuroda  (チェックアウト)
        │  scripts\server_deploy.py
        │    1. docker compose build   （資格情報ヘルパーを迂回）
        │    2. docker compose up -d
        │    3. ヘルスチェック → "Discord bot connected" をログで確認
        ▼
コンテナ butler-kuroda（イメージ docker-butler:latest）
```

- **コードは必ず GitHub 経由で届ける。** サーバー上のファイルを直接編集したり scp で
  上書きしたりしない（かつてそれで 7 か月分の差分がサーバーにだけ存在する状態になった）。
- **秘密情報（`.env`, `credentials/`）は Git 管理外**で、サーバー上のものを使い続ける。
- `scripts/deploy.py` がローカル側の入口、`scripts/server_deploy.py` がサーバー側の実体。

## 前提条件

- `ssh kusaka-server@192.168.68.79` が鍵認証で通ること
- サーバー側: Docker Desktop、Git、Python 3.13（`python` で起動できること）
- サーバー側チェックアウト: `C:\Users\kusaka-server\butler-kuroda`（origin = GitHub）

## 通常のデプロイ

```bash
# 1. 変更をコミットして push
git push origin main

# 2. デプロイ（取り込まれるコミットを表示し、確認後に実行）
python scripts/deploy.py

# 非対話で実行する場合
python scripts/deploy.py --yes
```

`deploy.py` が行うこと:

1. ローカルに未 push のコミットがあれば中止（サーバーは origin/main を取り込むため）
2. サーバーで `git fetch` し、取り込まれるコミット一覧を表示
3. サーバーで `git pull --ff-only --no-recurse-submodules origin main`
   - 作業ツリーに未コミット変更があれば中止。GitHub へ取り込んだ上で
     `--discard-local` を付けると破棄して続行
4. サーバーで `scripts\server_deploy.py --no-pull` を実行
   - ビルド前に現在のイメージ ID を表示（ロールバック用）
   - `docker compose build butler` → `docker compose up -d --no-build butler`
   - healthy になり、起動ログに `Discord bot connected` が出るまで待つ（最大 2 分ずつ）
   - 失敗時は直近ログを表示して非ゼロ終了

## その他の操作

| 目的 | コマンド |
|------|---------|
| 状態とログの確認 | `python scripts/deploy.py --status` |
| `.env` 変更の反映（ビルドなし） | `python scripts/deploy.py --restart-only` |
| 前のイメージに戻す | `python scripts/deploy.py --rollback <image-id>` |
| コミットが無くても再ビルド | `python scripts/deploy.py --force` |

サーバーにログインして直接実行する場合:

```bat
cd C:\Users\kusaka-server\butler-kuroda
python scripts\server_deploy.py            REM pull → build → up → 確認
python scripts\server_deploy.py --status
```

## .env の変更

`.env` はサーバー上の `C:\Users\kusaka-server\butler-kuroda\.env` だけに存在する。
変更したら `python scripts/deploy.py --restart-only` で再作成する（env はコンテナ作成時に固定されるため、`docker restart` では反映されない）。

主な変数（詳細は `.env.template`）:

| 変数名 | 説明 |
|--------|------|
| `DISCORD_BOT_TOKEN` / `DISCORD_GUILD_ID` / `DISCORD_OWNER_ID` | Discord 接続 |
| `GOOGLE_CALENDAR_ID` / `GOOGLE_CREDENTIALS_PATH` | Google Calendar |
| `ANTHROPIC_API_KEY` | Claude API キー |
| `CLAUDE_MODEL` | 使用モデル（省略時は `src/config/settings.py` の `DEFAULT_CLAUDE_MODEL`） |
| `ENABLE_SCHEDULED_JOBS` | `false` で朝の通知・週次イベント・法令情報・コーチングの定期ジョブを停止（コスト削減） |
| `USE_LANGGRAPH` | `true` で LangGraph エージェント（既定） |

### 注意: 編集時のエンコーディング

`.env` は UTF-8（BOM なし）・日本語を含む。Windows PowerShell の `Set-Content` は
BOM を付けることがあるので、エディタで UTF-8 のまま保存するか、ローカルへ scp して
編集して戻す。`certutil -encode/-decode` は日本語を壊す。

## モデル提供終了への対応

Claude のモデル ID は提供終了すると API が `404 not_found_error` を返し、黒田は
「ただいま処理に問題が発生いたしました」とだけ答える。対処:

1. `src/config/settings.py` の `DEFAULT_CLAUDE_MODEL` を現行モデルに更新してコミット
2. サーバーの `.env` に `CLAUDE_MODEL` があれば同じ値に更新
3. `python scripts/deploy.py`

モデル ID は `settings.py` の 1 か所で管理し、`claude.py` / `graph.py` はそこから import する。
LangGraph 経路も `Butler.handle_message` から `settings.claude_model` を受け取る。

## なぜ資格情報ヘルパーを迂回するのか

SSH セッションから `docker compose build` を実行すると、Docker CLI が
`docker-credential-desktop`（または PATH 上の `docker-credential-wincred`）を呼び、
対話ログオンセッションが無いため次のエラーで失敗する:

```
error getting credentials - err: exit status 1,
out: `A specified logon session does not exist. It may already have been terminated.`
```

`server_deploy.py` はビルドの間だけ、

1. 資格情報ストア設定を持たない一時ディレクトリを `DOCKER_CONFIG` に指定し
   （`contexts` は実際の設定からコピー）、
2. `PATH` から Docker の `bin` を外して `docker.exe` をフルパスで呼ぶ

ことで回避する。Docker Desktop 自体の設定は変更しない。ベースイメージ
`python:3.11-slim` は匿名で pull できる。

## トラブルシューティング

### `git pull` が「未コミットの変更があります」で止まる

サーバー上で直接ファイルが編集されている。内容を確認し、必要なら GitHub 側に
取り込んだ上で `python scripts/deploy.py --discard-local`。

```bash
ssh kusaka-server@192.168.68.79 "git -C C:\Users\kusaka-server\butler-kuroda diff"
```

### Discord 接続待機でタイムアウトする

```bash
ssh kusaka-server@192.168.68.79 "docker logs butler-kuroda --tail 50"
```

トークン失効なら `LoginFailure`、依存関係の問題なら `Traceback` が出る。
直前のイメージに戻すには `server_deploy.py` が表示したイメージ ID で
`python scripts/deploy.py --rollback <image-id>`。

### 「処理に問題が発生いたしました」と返る

Agent ノードの例外。ログの `Agent node failed` 行に原因（`404 not_found_error` なら
モデル提供終了、`401` なら API キー）が出る。

```bash
ssh kusaka-server@192.168.68.79 "docker logs --since 10m butler-kuroda"
```

## サーバー情報

| 項目 | 値 |
|------|-----|
| ホスト | `kusaka-server@192.168.68.79` |
| OS | Windows 11 + Docker Desktop |
| チェックアウト | `C:\Users\kusaka-server\butler-kuroda` |
| compose | `docker\docker-compose.yml`（project 名 `docker`） |
| コンテナ / イメージ | `butler-kuroda` / `docker-butler:latest` |
| ログ | `docker logs butler-kuroda`（json-file 10MB × 3） |

---

*最終更新: 2026-10-25*
