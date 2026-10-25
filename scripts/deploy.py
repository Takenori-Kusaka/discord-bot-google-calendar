#!/usr/bin/env python3
"""執事「黒田」デプロイスクリプト（ローカルで実行する）

GitHub の main をソース・オブ・トゥルースとして、サーバー上のチェックアウトを
更新し、Docker イメージを再ビルドしてコンテナを再作成する。

    python scripts/deploy.py                 # 確認プロンプトあり
    python scripts/deploy.py --yes           # 非対話
    python scripts/deploy.py --restart-only  # .env 変更の反映など（ビルドなし）
    python scripts/deploy.py --status        # サーバーの状態とログ
    python scripts/deploy.py --rollback <image-id>

流れ:
  1. ローカル: 未コミット / 未 push の変更がないか確認（サーバーは origin/main を取り込む）
  2. サーバー: git pull --ff-only（作業ツリーが汚れていれば中止。--discard-local で破棄）
  3. サーバー: scripts/server_deploy.py --no-pull を実行
       → 資格情報ヘルパーを迂回して docker compose build → up -d → ヘルスチェック
         → Discord 接続ログの確認
  4. 状態とログを表示

秘密情報（.env, credentials/）は Git 管理外で、サーバー上のものをそのまま使う。
.env を変えたときは --restart-only で再作成すれば反映される。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SSH_TARGET = "kusaka-server@192.168.68.79"
REMOTE_REPO = r"C:\Users\kusaka-server\butler-kuroda"
REMOTE_PYTHON = "python"
LOCAL_REPO = Path(__file__).resolve().parents[1]
SSH_BASE = ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", SSH_TARGET]


def log(msg: str) -> None:
    print(f"[deploy] {msg}", flush=True)


def die(msg: str, code: int = 1) -> None:
    print(f"[deploy] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def local_git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(LOCAL_REPO), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.strip()


def ssh(remote_cmd: str, capture: bool = False) -> subprocess.CompletedProcess:
    """リモート（Windows / cmd.exe）でコマンドを実行する"""
    return subprocess.run(
        [*SSH_BASE, remote_cmd],
        check=False,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def remote_git(args: str, capture: bool = True) -> subprocess.CompletedProcess:
    return ssh(f'git -C "{REMOTE_REPO}" {args}', capture=capture)


def confirm(prompt: str, auto_yes: bool) -> None:
    if auto_yes:
        return
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    if answer not in ("y", "yes"):
        die("中止しました", code=0)


def check_local_state(skip: bool) -> None:
    if skip:
        return
    dirty = local_git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        log("警告: ローカルに未コミットの変更があります（サーバーには反映されません）")
        print(dirty)
    local_git("fetch", "-q", "origin")
    unpushed = local_git("rev-list", "--count", "origin/main..HEAD")
    if unpushed != "0":
        die(
            f"未 push のコミットが {unpushed} 件あります。"
            "サーバーは origin/main を取り込むので、先に git push してください。"
        )
    if local_git("rev-parse", "HEAD") != local_git("rev-parse", "origin/main"):
        log(
            "注意: ローカル HEAD は origin/main と一致しません。デプロイされるのは origin/main です。"
        )


def check_connection() -> None:
    log(f"SSH 接続確認: {SSH_TARGET}")
    res = ssh("echo ok", capture=True)
    if res.returncode != 0 or "ok" not in res.stdout:
        die(f"サーバーに接続できません: {res.stderr.strip()}")


def show_incoming() -> bool:
    """サーバーに取り込まれるコミットを表示し、あるかどうかを返す"""
    res = remote_git("fetch -q origin")
    if res.returncode != 0:
        die("サーバー側 git fetch に失敗: " + res.stderr.strip())
    head = remote_git("log -1 --format=%h_%s").stdout.strip()
    incoming = remote_git("log --oneline HEAD..origin/main").stdout.strip()
    log(f"サーバーの現在の HEAD: {head}")
    if incoming:
        log("取り込まれるコミット:")
        print(incoming)
        return True
    log("サーバーは既に origin/main と同じです")
    return False


def remove_untracked_conflicts() -> None:
    """origin/main に含まれるのにサーバーで未追跡のファイルを削除する

    かつて scp で配置されたファイルが残っていると
    "untracked working tree files would be overwritten by merge" で pull が止まるため。
    """
    untracked = set(remote_git("ls-files --others --exclude-standard").stdout.split())
    tracked_in_main = set(
        remote_git("ls-tree -r --name-only origin/main").stdout.split()
    )
    conflicts = sorted(untracked & tracked_in_main)
    if not conflicts:
        return
    log("origin/main と衝突する未追跡ファイルを削除します: " + ", ".join(conflicts))
    remote_git("clean -f -- " + " ".join(f'"{c}"' for c in conflicts))


def remote_pull(discard_local: bool) -> None:
    dirty = remote_git("status --porcelain --untracked-files=no").stdout.strip()
    if dirty:
        print(dirty)
        if not discard_local:
            die(
                "サーバーの作業ツリーに未コミットの変更があります。"
                "内容を GitHub に取り込んでから --discard-local で破棄してください。"
            )
        log("サーバー側のローカル変更を破棄します")
        remote_git("checkout -- .")
    if discard_local:
        remove_untracked_conflicts()
    log("サーバー: git pull --ff-only")
    res = remote_git(
        "pull --ff-only --no-recurse-submodules origin main", capture=False
    )
    if res.returncode != 0:
        die("git pull に失敗しました")


def run_server_deploy(*flags: str) -> None:
    cmd = (
        f'cd /d "{REMOTE_REPO}" && {REMOTE_PYTHON} scripts\\server_deploy.py '
        + " ".join(flags)
    )
    log("サーバー: " + cmd)
    res = ssh(cmd)
    if res.returncode != 0:
        die(f"server_deploy.py が失敗しました (exit {res.returncode})")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-y", "--yes", action="store_true", help="確認なしで実行")
    ap.add_argument("--restart-only", action="store_true", help="ビルドせず再作成のみ")
    ap.add_argument("--status", action="store_true", help="状態表示のみ")
    ap.add_argument("--rollback", metavar="IMAGE_ID", help="指定イメージに戻す")
    ap.add_argument(
        "--discard-local",
        action="store_true",
        help="サーバー側の未コミット変更を破棄して pull する",
    )
    ap.add_argument(
        "--skip-git-check", action="store_true", help="ローカルの git 状態確認を省略"
    )
    ap.add_argument(
        "--force", action="store_true", help="取り込むコミットが無くても再ビルドする"
    )
    args = ap.parse_args()

    check_connection()

    if args.status:
        run_server_deploy("--status")
        return
    if args.rollback:
        confirm(f"{args.rollback} にロールバックしますか?", args.yes)
        run_server_deploy("--rollback", args.rollback)
        return
    if args.restart_only:
        confirm("コンテナを再作成しますか?（ビルドなし）", args.yes)
        run_server_deploy("--restart-only")
        return

    check_local_state(args.skip_git_check)
    has_incoming = show_incoming()
    if not has_incoming and not args.force:
        confirm("新しいコミットはありません。それでも再ビルドしますか?", args.yes)
    else:
        confirm("デプロイを実行しますか?", args.yes)

    remote_pull(args.discard_local)
    run_server_deploy("--no-pull")
    log("完了")


if __name__ == "__main__":
    main()
