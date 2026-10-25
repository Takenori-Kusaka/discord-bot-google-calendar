#!/usr/bin/env python3
"""執事「黒田」サーバー側デプロイスクリプト（kusaka-server 上で実行する）

ローカルからは scripts/deploy.py 経由で呼び出される。サーバーに直接ログインして
手動で実行してもよい。

    python scripts\\server_deploy.py                 # pull → build → up → 疎通確認
    python scripts\\server_deploy.py --no-pull       # 作業ツリーをそのままビルド
    python scripts\\server_deploy.py --restart-only  # 再作成のみ（.env 変更の反映など）
    python scripts\\server_deploy.py --status        # 状態とログの表示のみ
    python scripts\\server_deploy.py --rollback <image-id>

なぜこのスクリプトが必要か
--------------------------
サーバーは Windows + Docker Desktop で、SSH セッションから ``docker compose build`` を
実行すると、Docker CLI が資格情報ヘルパー（docker-credential-desktop / wincred）を
呼び出し、対話ログオンセッションが無いために失敗する::

    error getting credentials - err: exit status 1,
    out: `A specified logon session does not exist.`

本スクリプトはビルド時だけ以下を行って回避する（Docker Desktop の設定は変更しない）。

1. 資格情報ストアを持たない一時的な DOCKER_CONFIG を用意する（contexts はコピー）
2. PATH から Docker の bin ディレクトリを外し、docker.exe はフルパスで呼ぶ
   （PATH 上に docker-credential-wincred があると既定の保存先として使われるため）

ベースイメージ（python:3.11-slim）は匿名 pull できるので資格情報は不要。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
COMPOSE_DIR = REPO_DIR / "docker"
SERVICE = "butler"
CONTAINER = "butler-kuroda"
IMAGE = "docker-butler:latest"
READY_LOG_MARKER = "Discord bot connected"
HEALTH_TIMEOUT_SEC = 120
READY_TIMEOUT_SEC = 120


def log(msg: str) -> None:
    print(f"[server-deploy] {msg}", flush=True)


def die(msg: str, code: int = 1) -> None:
    print(f"[server-deploy] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Docker 実行環境（資格情報ヘルパー回避）
# ---------------------------------------------------------------------------


class DockerRunner:
    """資格情報ヘルパーを迂回した環境で docker を実行する"""

    def __init__(self) -> None:
        docker = shutil.which("docker")
        if not docker:
            die("docker が見つかりません")
        self.docker = docker
        self._tmpdir = tempfile.TemporaryDirectory(prefix="butler-docker-config-")
        self.env = self._build_env(Path(self._tmpdir.name))

    def _build_env(self, config_dir: Path) -> dict[str, str]:
        env = dict(os.environ)

        # 1) 資格情報ストアを持たない DOCKER_CONFIG
        real_config_dir = Path(os.environ.get("DOCKER_CONFIG", Path.home() / ".docker"))
        current_context = "desktop-linux"
        real_config = real_config_dir / "config.json"
        if real_config.exists():
            try:
                current_context = json.loads(
                    real_config.read_text(encoding="utf-8")
                ).get("currentContext", current_context)
            except (OSError, ValueError):
                pass
        (config_dir / "config.json").write_text(
            json.dumps({"auths": {}, "currentContext": current_context}),
            encoding="utf-8",
        )
        contexts = real_config_dir / "contexts"
        if contexts.is_dir():
            shutil.copytree(contexts, config_dir / "contexts")
        env["DOCKER_CONFIG"] = str(config_dir)

        # 2) PATH から Docker の bin を外す（docker.exe はフルパスで呼ぶ）
        docker_bin = str(Path(self.docker).parent).lower()
        kept = [
            p
            for p in os.environ.get("PATH", "").split(os.pathsep)
            if p and p.lower().rstrip("\\/") != docker_bin.rstrip("\\/")
        ]
        env["PATH"] = os.pathsep.join(kept)
        return env

    def run(
        self,
        *args: str,
        cwd: Path | None = None,
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess:
        cmd = [self.docker, *args]
        return subprocess.run(
            cmd,
            cwd=cwd,
            env=self.env,
            check=check,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def out(self, *args: str, check: bool = True) -> str:
        return self.run(*args, check=check, capture=True).stdout.strip()

    def compose(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return self.run("compose", *args, cwd=COMPOSE_DIR, check=check)


# ---------------------------------------------------------------------------
# git
# ---------------------------------------------------------------------------


def git(*args: str, check: bool = True) -> str:
    res = subprocess.run(
        ["git", "-C", str(REPO_DIR), *args],
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return res.stdout.strip()


def git_pull(discard_local: bool) -> None:
    dirty = git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        if not discard_local:
            die(
                "サーバーの作業ツリーに未コミットの変更があります。\n"
                + dirty
                + "\n変更は GitHub 側へ取り込んでから、--discard-local で破棄してください。"
            )
        log("ローカル変更を破棄します (git checkout -- .)")
        git("checkout", "--", ".")

    log("git fetch origin")
    git("fetch", "origin")
    if discard_local:
        # origin/main に含まれるのに未追跡のファイル（過去に scp で配置されたもの）が
        # あると "would be overwritten by merge" で止まるので、それだけ削除する
        untracked = set(git("ls-files", "--others", "--exclude-standard").split())
        in_main = set(git("ls-tree", "-r", "--name-only", "origin/main").split())
        conflicts = sorted(untracked & in_main)
        if conflicts:
            log("衝突する未追跡ファイルを削除: " + ", ".join(conflicts))
            git("clean", "-f", "--", *conflicts)
    incoming = git("log", "--oneline", "HEAD..origin/main")
    if incoming:
        log("取り込むコミット:\n" + incoming)
    else:
        log("サーバーは既に origin/main と同じです")
    git("pull", "--ff-only", "--no-recurse-submodules", "origin", "main")
    log("HEAD = " + git("log", "-1", "--format=%h %s"))


# ---------------------------------------------------------------------------
# デプロイ手順
# ---------------------------------------------------------------------------


def current_image_id(d: DockerRunner) -> str | None:
    res = d.run(
        "image", "inspect", IMAGE, "--format", "{{.Id}}", check=False, capture=True
    )
    return res.stdout.strip() if res.returncode == 0 else None


def build(d: DockerRunner) -> None:
    previous = current_image_id(d)
    if previous:
        log(f"ロールバック用: 現在のイメージ {previous}")
    log("docker compose build")
    d.compose("build", SERVICE)


def up(d: DockerRunner, force_recreate: bool) -> None:
    args = ["up", "-d", "--no-build"]
    if force_recreate:
        args.append("--force-recreate")
    log("docker compose " + " ".join(args))
    d.compose(*args, SERVICE)


def wait_for_ready(d: DockerRunner) -> None:
    started_at = d.out("inspect", "--format", "{{.State.StartedAt}}", CONTAINER)

    log("ヘルスチェック待機中...")
    deadline = time.time() + HEALTH_TIMEOUT_SEC
    while time.time() < deadline:
        state = d.out(
            "inspect",
            "--format",
            "{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
            CONTAINER,
        )
        if state in ("running/healthy", "running/none"):
            break
        if state.startswith("exited"):
            show_logs(d, 40)
            die("コンテナが終了しました")
        time.sleep(3)
    else:
        show_logs(d, 40)
        die("ヘルスチェックがタイムアウトしました")
    log(f"コンテナ状態: {state}")

    log(f"Discord 接続待機中 ('{READY_LOG_MARKER}' をログで確認)...")
    deadline = time.time() + READY_TIMEOUT_SEC
    while time.time() < deadline:
        logs = d.run(
            "logs", "--since", started_at, CONTAINER, check=False, capture=True
        )
        combined = logs.stdout + logs.stderr
        if READY_LOG_MARKER in combined:
            log("Discord 接続を確認しました")
            return
        if "Traceback" in combined or "LoginFailure" in combined:
            show_logs(d, 40)
            die("起動ログにエラーがあります")
        time.sleep(5)
    show_logs(d, 40)
    die("Discord 接続をログで確認できませんでした")


def show_logs(d: DockerRunner, tail: int) -> None:
    print(f"----- docker logs --tail {tail} {CONTAINER} -----", flush=True)
    d.run("logs", "--tail", str(tail), CONTAINER, check=False)
    print("----- end of logs -----", flush=True)


def status(d: DockerRunner) -> None:
    d.run(
        "ps",
        "-a",
        "--filter",
        f"name={CONTAINER}",
        "--format",
        "table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.CreatedAt}}",
        check=False,
    )
    print("HEAD:", git("log", "-1", "--format=%h %cd %s", check=False), flush=True)
    show_logs(d, 15)


def rollback(d: DockerRunner, image_id: str) -> None:
    log(f"{image_id} を {IMAGE} としてタグ付けして再作成します")
    d.run("tag", image_id, IMAGE)
    up(d, force_recreate=True)
    wait_for_ready(d)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-pull", action="store_true", help="git pull を行わない")
    ap.add_argument(
        "--discard-local",
        action="store_true",
        help="サーバー側の未コミット変更を破棄して pull する",
    )
    ap.add_argument(
        "--restart-only",
        action="store_true",
        help="ビルドせずコンテナを再作成する（.env 変更の反映など）",
    )
    ap.add_argument("--status", action="store_true", help="状態表示のみ")
    ap.add_argument("--rollback", metavar="IMAGE_ID", help="指定イメージに戻す")
    args = ap.parse_args()

    d = DockerRunner()

    if args.status:
        status(d)
        return
    if args.rollback:
        rollback(d, args.rollback)
        status(d)
        return
    if args.restart_only:
        up(d, force_recreate=True)
        wait_for_ready(d)
        status(d)
        return

    if not args.no_pull:
        git_pull(discard_local=args.discard_local)
    build(d)
    up(d, force_recreate=False)
    wait_for_ready(d)
    status(d)
    log("デプロイ完了")


if __name__ == "__main__":
    main()
