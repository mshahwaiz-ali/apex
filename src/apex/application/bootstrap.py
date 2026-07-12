"""Application bootstrap orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from apex.config import FileSettings, load_settings
from apex.monitoring import configure_logging


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    settings: FileSettings


def bootstrap() -> ApplicationContext:
    """Load validated settings and initialize process-wide services."""

    settings = load_settings()
    configure_logging(settings.log_level, settings.log_dir)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return ApplicationContext(settings=settings)
