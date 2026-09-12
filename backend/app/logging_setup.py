"""Application logging setup (F-14).

Uvicorn configures only its own loggers; without an explicit handler the
``ecoleak`` loggers fall through to ``logging.lastResort`` (WARNING+ to
stderr), which silently drops the INFO request lines. This attaches one
stderr handler so request/error logs are actually observable, with the level
overridable via ``LOG_LEVEL``.
"""
from __future__ import annotations

import logging
import os

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger("ecoleak")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(handler)
    logger.propagate = False
    _CONFIGURED = True
