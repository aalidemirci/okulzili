from __future__ import annotations

from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


def configure_logging(
    log_path: Path,
    max_bytes: int = 2_000_000,
    backup_count: int = 5,
) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("okul_zili")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    resolved = log_path.resolve()
    for existing in list(logger.handlers):
        if (
            isinstance(existing, RotatingFileHandler)
            and Path(existing.baseFilename).resolve() == resolved
            and existing.maxBytes == max_bytes
            and existing.backupCount == backup_count
        ):
            return logger
        logger.removeHandler(existing)
        existing.close()
    handler = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def log_event(logger: logging.Logger, event: str, level: str = "bilgi", **details: Any) -> None:
    payload = {
        **details,
        "zaman": datetime.now().astimezone().isoformat(timespec="seconds"),
        "seviye": level,
        "olay": event,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))
