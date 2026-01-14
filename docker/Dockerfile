FROM python:3.11-slim

# 作業ディレクトリ設定
WORKDIR /app

# システム依存パッケージ
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Poetry インストール
RUN pip install --no-cache-dir poetry

# 依存関係ファイルをコピー
COPY pyproject.toml poetry.lock* ./

# 依存関係インストール（開発依存を除く）
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

# アプリケーションコード
COPY src/ ./src/
COPY config/ ./config/

# ログディレクトリ作成
RUN mkdir -p /app/logs

# 非rootユーザーで実行
RUN useradd -m butler
RUN chown -R butler:butler /app
USER butler

# 実行
CMD ["python", "-m", "src.main"]
