@echo off
REM 執事「黒田」デプロイスクリプト (Windows版)
REM Usage: scripts\deploy.bat [--restart-only]

setlocal enabledelayedexpansion

set SERVER=kusaka-server@192.168.68.79
set REMOTE_DIR=butler-kuroda
set PROJECT_ROOT=%~dp0..

echo ==========================================
echo   執事「黒田」デプロイスクリプト
echo ==========================================
echo.

REM SSH接続テスト
echo [INFO] SSHサーバーへの接続を確認中...
ssh -o ConnectTimeout=10 -o BatchMode=yes %SERVER% "echo ok" > nul 2>&1
if errorlevel 1 (
    echo [ERROR] サーバーに接続できません: %SERVER%
    exit /b 1
)
echo [INFO] 接続OK

REM 再起動のみの場合
if "%1"=="--restart-only" (
    echo [INFO] コンテナを再起動中...
    ssh %SERVER% "cd %REMOTE_DIR%/docker && docker-compose restart"
    goto :status
)

REM ファイル転送
echo [INFO] ファイルを転送中...
scp -r "%PROJECT_ROOT%\src" "%PROJECT_ROOT%\config" "%PROJECT_ROOT%\docker" "%PROJECT_ROOT%\credentials" "%PROJECT_ROOT%\pyproject.toml" "%PROJECT_ROOT%\poetry.lock" "%PROJECT_ROOT%\.env" %SERVER%:~/%REMOTE_DIR%/

if errorlevel 1 (
    echo [ERROR] ファイル転送に失敗しました
    exit /b 1
)
echo [INFO] 転送完了

REM Dockerビルド・起動
echo [INFO] Dockerコンテナをビルド・起動中...
ssh %SERVER% "cd %REMOTE_DIR%/docker && docker-compose up -d --build"

if errorlevel 1 (
    echo [ERROR] Dockerデプロイに失敗しました
    exit /b 1
)
echo [INFO] デプロイ完了

:status
REM ステータス確認
echo.
echo === コンテナ状態 ===
ssh %SERVER% "docker ps --filter name=butler-kuroda"

echo.
echo === 最新ログ ===
ssh %SERVER% "docker logs butler-kuroda --tail 10"

echo.
echo [INFO] デプロイが完了しました！

endlocal
