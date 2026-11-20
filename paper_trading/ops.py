"""Operational helpers for safe paper-trading runs."""
from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")


def configure_logging(log_path: str | Path, level: int = logging.INFO) -> logging.Logger:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("mabot.paper")
    logger.setLevel(level)
    logger.propagate = False
    # Avoid duplicate handlers when tests or repeated runner instances configure logging.
    if not any(getattr(h, "baseFilename", None) == str(path.resolve()) for h in logger.handlers):
        handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
        logger.addHandler(handler)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
               for h in logger.handlers):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(console)
    return logger


def retry_call(call: Callable[[], T], attempts: int = 3,
               base_delay: float = 1.0, max_delay: float = 8.0,
               sleep: Callable[[float], None] = time.sleep) -> T:
    """Retry transient read-only operations with capped exponential backoff."""
    if attempts < 1 or base_delay < 0 or max_delay < 0:
        raise ValueError("Invalid retry policy")
    for attempt in range(attempts):
        try:
            return call()
        except Exception:
            if attempt + 1 >= attempts:
                raise
            sleep(min(base_delay * (2 ** attempt), max_delay))
    raise RuntimeError("unreachable")
