#!/bin/bash
# 執事「黒田」デプロイスクリプト
# Usage: ./scripts/deploy.sh [--restart-only]

set -e

# 設定
SERVER="kusaka-server@192.168.68.79"
REMOTE_DIR="butler-kuroda"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 色付きログ
log_info() { echo -e "\033[0;32m[INFO]\033[0m $1"; }
log_warn() { echo -e "\033[0;33m[WARN]\033[0m $1"; }
log_error() { echo -e "\033[0;31m[ERROR]\033[0m $1"; }

# SSH接続テスト
check_connection() {
    log_info "SSHサーバーへの接続を確認中..."
    if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$SERVER" "echo ok" > /dev/null 2>&1; then
        log_error "サーバーに接続できません: $SERVER"
        exit 1
    fi
    log_info "接続OK"
}

# ファイル転送
transfer_files() {
    log_info "ファイルを転送中..."

    # 必要なファイルのみ転送
    scp -r \
        "$PROJECT_ROOT/src" \
        "$PROJECT_ROOT/config" \
        "$PROJECT_ROOT/docker" \
        "$PROJECT_ROOT/credentials" \
        "$PROJECT_ROOT/pyproject.toml" \
        "$PROJECT_ROOT/poetry.lock" \
        "$PROJECT_ROOT/.env" \
        "$SERVER:~/$REMOTE_DIR/"

    log_info "転送完了"
}

# Dockerビルド・起動
deploy_docker() {
    log_info "Dockerコンテナをビルド・起動中..."

    ssh "$SERVER" "cd $REMOTE_DIR/docker && docker-compose up -d --build"

    log_info "デプロイ完了"
}

# 再起動のみ
restart_only() {
    log_info "コンテナを再起動中..."
    ssh "$SERVER" "cd $REMOTE_DIR/docker && docker-compose restart"
    log_info "再起動完了"
}

# ステータス確認
check_status() {
    log_info "ステータス確認中..."

    echo ""
    echo "=== コンテナ状態 ==="
    ssh "$SERVER" "docker ps --filter name=butler-kuroda --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

    echo ""
    echo "=== 最新ログ ==="
    ssh "$SERVER" "docker logs butler-kuroda --tail 10 2>&1" || true
}

# メイン
main() {
    echo "=========================================="
    echo "  執事「黒田」デプロイスクリプト"
    echo "=========================================="
    echo ""

    check_connection

    if [ "$1" == "--restart-only" ]; then
        restart_only
    else
        transfer_files
        deploy_docker
    fi

    check_status

    echo ""
    log_info "デプロイが完了しました！"
}

main "$@"
