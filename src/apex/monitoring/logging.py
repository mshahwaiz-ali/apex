"""Central logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

_THIRD_PARTY_LOG_LEVELS: dict[str, int] = {
    "httpcore": logging.WARNING,
    "httpx": logging.WARNING,
}


def configure_logging(level: str, log_dir: Path) -> None:
    """Configure console and file logging for the process."""

    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(log_dir / "apex.log", encoding="utf-8"),
    ]
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
        force=True,
    )
    for logger_name, logger_level in _THIRD_PARTY_LOG_LEVELS.items():
        logging.getLogger(logger_name).setLevel(logger_level)
