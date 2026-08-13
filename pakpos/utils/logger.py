"""
Application logger.
Logs to rotating file in LOG_DIR and to console during development.
Never log passwords, credentials, or sensitive customer data.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from pakpos.config.settings import LOG_DIR

_initialized = False


def _init_logging() -> None:
    global _initialized
    if _initialized:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "pakpos.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler — 5 MB per file, keep 10 files
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler (INFO+ only)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    _init_logging()
    return logging.getLogger(name)
