"""ログ設定"""

import logging
import sys
from pathlib import Path

import structlog


def setup_logger(log_level: str = "INFO", log_dir: Path | None = None) -> None:
    """ログを設定する

    Args:
        log_level: ログレベル（DEBUG, INFO, WARNING, ERROR）
        log_dir: ログ出力ディレクトリ（Noneの場合は標準出力のみ）
    """
    # ログレベル設定
    level = getattr(logging, log_level.upper(), logging.INFO)

    # 標準ログ設定
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # ファイル出力設定
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / "butler.log",
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        logging.getLogger().addHandler(file_handler)

    # structlog設定
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """ロガーを取得する

    Args:
        name: ロガー名

    Returns:
        structlog.BoundLogger: ロガー
    """
    return structlog.get_logger(name)
