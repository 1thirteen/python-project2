"""日志：写到 logs/app.log，界面与命令行共用；出错时同时打一份到控制台。"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from common.config import ROOT

LOG_DIR = ROOT / "logs"
_configured = False


def setup(level: str = "INFO") -> logging.Logger:
    """初始化根 logger（幂等）。"""
    global _configured
    logger = logging.getLogger("student")
    if _configured:
        return logger
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    LOG_DIR.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(console)

    logger.propagate = False
    _configured = True
    return logger


def get(name: str = "student") -> logging.Logger:
    return setup() if not _configured else logging.getLogger(name)
