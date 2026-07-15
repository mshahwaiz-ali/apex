"""Load deterministic lifecycle health evidence from paper pipeline audits."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any

from apex.application.paper_lifecycle_analytics import (
    PaperLifecycleAnalytics,
    PaperLifecycleTradeRecord,
)
from apex.application.paper_lifecycle_health import (
    PaperLifecycleHealthPolicy,
    PaperLifecycleHealthReport,
    evaluate_paper_lifecycle_health,
)
from apex.paper_trading.intake import IntakeMarketType

__all__ = [
    "PaperLifecycleHealthAudit",
    "load_latest_paper_lifecycle_health",
]


@dataclass(frozen=True, slots=True)
class PaperLifecycleHealthAudit:
    """Health report tied to one successful scheduled pipeline audit record."""

    run_id: str
    market_type: IntakeMarketType
    completed_at: datetime
    log_path: str
    analytics: PaperLifecycleAnalytics
    health: PaperLifecycleHealthReport


def load_latest_paper_lifecycle_health(
    path: Path,
    *,
    market_type: IntakeMarketType,
    policy: PaperLifecycleHealthPolicy | None = None,
) -> PaperLifecycleHealthAudit:
    """Load and evaluate the latest successful analytics-bearing pipeline record."""

    if not path.exists():
        raise FileNotFoundError(f"paper pipeline audit log does not exist: {path}")

    latest: dict[str, Any] | None = None
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in paper pipeline audit line {line_number}") from exc
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            raise TypeError(f"paper pipeline audit line {line_number} must be a JSON object")
        payload = dict(value)
        if payload.get("outcome") != "success":
            continue
        if str(payload.get("market_type", "")).strip().lower() != market_type.value:
            continue
        analytics = payload.get("lifecycle_analytics")
        if not isinstance(analytics, dict) or not analytics:
            continue
        latest = payload

    if latest is None:
        raise ValueError(
            f"no successful analytics-bearing {market_type.value} pipeline record found in {path}"
        )

    run_id = str(latest.get("run_id", "")).strip()
    if not run_id:
        raise ValueError("paper pipeline audit run_id cannot be empty")
    completed_at = _parse_datetime(latest.get("completed_at"), "completed_at")
    analytics = _analytics_from_payload(latest["lifecycle_analytics"])
    return PaperLifecycleHealthAudit(
        run_id=run_id,
        market_type=market_type,
        completed_at=completed_at,
        log_path=str(path),
        analytics=analytics,
        health=evaluate_paper_lifecycle_health(analytics, policy=policy),
    )


def _analytics_from_payload(value: object) -> PaperLifecycleAnalytics:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("lifecycle analytics must be a JSON object")
    payload = dict(value)
    expected = {field.name for field in fields(PaperLifecycleAnalytics)}
    missing = sorted(expected - payload.keys())
    extra = sorted(payload.keys() - expected)
    if missing:
        raise ValueError(f"lifecycle analytics missing fields: {', '.join(missing)}")
    if extra:
        raise ValueError(f"lifecycle analytics contains unknown fields: {', '.join(extra)}")

    trades_value = payload["trades"]
    if not isinstance(trades_value, list):
        raise TypeError("lifecycle analytics trades must be a JSON list")
    payload["trades"] = tuple(_trade_record_from_payload(item) for item in trades_value)
    return PaperLifecycleAnalytics(**payload)


def _trade_record_from_payload(value: object) -> PaperLifecycleTradeRecord:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("lifecycle analytics trade records must be JSON objects")
    payload = dict(value)
    expected = {field.name for field in fields(PaperLifecycleTradeRecord)}
    missing = sorted(expected - payload.keys())
    extra = sorted(payload.keys() - expected)
    if missing:
        raise ValueError(f"lifecycle trade record missing fields: {', '.join(missing)}")
    if extra:
        raise ValueError(f"lifecycle trade record contains unknown fields: {', '.join(extra)}")
    return PaperLifecycleTradeRecord(**payload)


def _parse_datetime(value: object, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"paper pipeline audit {field_name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"paper pipeline audit {field_name} must be timezone-aware")
    return parsed
