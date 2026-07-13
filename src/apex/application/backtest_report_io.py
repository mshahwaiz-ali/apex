"""Stable JSON serialization for chronological backtest reports."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


def make_run_id(*, symbol: str, replay_timeframe: str, dataset_hash: str, config_hash: str) -> str:
    """Create a stable, readable identity for a baseline run."""
    slug = symbol.lower().replace("/", "-").replace("_", "-")
    timeframe = replay_timeframe.lower().replace("/", "-")
    return f"{slug}-{timeframe}-{dataset_hash[:12]}-{config_hash[:12]}"


def to_json_value(value: Any) -> Any:
    """Convert supported domain values into explicit JSON-compatible values."""
    if is_dataclass(value) and not isinstance(value, type):
        return to_json_value(asdict(value))
    if isinstance(value, Enum):
        return to_json_value(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("report datetimes must be timezone-aware")
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported report value: {type(value).__name__}")


def dumps_report(payload: Any) -> str:
    """Serialize a report deterministically with explicit type conversion."""
    return json.dumps(to_json_value(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_backtest_report(path: Path, payload: Any, *, force: bool = False) -> None:
    """Atomically write a report while protecting existing files."""
    if path.exists() and not force:
        raise ValueError(f"refusing to overwrite existing report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(dumps_report(payload), encoding="utf-8")
    temporary.replace(path)


def load_backtest_report(path: Path) -> dict[str, Any]:
    """Load one saved JSON report."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid backtest report {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("backtest report must contain a JSON object")
    return payload
