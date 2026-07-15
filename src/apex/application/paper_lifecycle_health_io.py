"""Load and persist deterministic lifecycle health evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, cast

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

PAPER_LIFECYCLE_HEALTH_ARTIFACT_SCHEMA_VERSION = 1

__all__ = [
    "PAPER_LIFECYCLE_HEALTH_ARTIFACT_SCHEMA_VERSION",
    "PaperLifecycleHealthArtifact",
    "PaperLifecycleHealthAudit",
    "build_paper_lifecycle_health_artifact",
    "load_and_verify_paper_lifecycle_health_artifact",
    "load_latest_paper_lifecycle_health",
    "write_paper_lifecycle_health_artifact",
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


@dataclass(frozen=True, slots=True)
class PaperLifecycleHealthArtifact:
    """Hash-verified lifecycle-health evidence artifact."""

    payload: dict[str, Any]
    report_sha256: str


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


def build_paper_lifecycle_health_artifact(
    audit: PaperLifecycleHealthAudit,
    *,
    policy: PaperLifecycleHealthPolicy,
) -> PaperLifecycleHealthArtifact:
    """Build a deterministic, reproducible lifecycle-health artifact."""

    payload: dict[str, Any] = {
        "schema_version": PAPER_LIFECYCLE_HEALTH_ARTIFACT_SCHEMA_VERSION,
        "source": {
            "run_id": audit.run_id,
            "market_type": audit.market_type.value,
            "completed_at": audit.completed_at.isoformat(),
            "log_path": audit.log_path,
        },
        "policy": asdict(policy),
        "health": _jsonable(asdict(audit.health)),
        "analytics": _jsonable(asdict(audit.analytics)),
        "execution_authorized": False,
        "warnings": [
            "This artifact records forward-paper lifecycle evidence only.",
            "It does not authorize testnet or real-money execution.",
        ],
    }
    report_hash = _hash_payload(payload)
    payload["report_sha256"] = report_hash
    return PaperLifecycleHealthArtifact(payload=payload, report_sha256=report_hash)


def write_paper_lifecycle_health_artifact(
    artifact: PaperLifecycleHealthArtifact,
    path: Path,
    *,
    force: bool = False,
) -> None:
    """Persist a lifecycle-health artifact atomically without silent overwrite."""

    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite lifecycle-health artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(artifact.payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_and_verify_paper_lifecycle_health_artifact(
    path: Path,
) -> PaperLifecycleHealthArtifact:
    """Reload a lifecycle-health artifact and verify its payload hash."""

    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("lifecycle-health artifact must be a JSON object")
    payload = cast(dict[str, Any], dict(value))
    schema_version = payload.get("schema_version")
    if schema_version != PAPER_LIFECYCLE_HEALTH_ARTIFACT_SCHEMA_VERSION:
        raise ValueError(f"unsupported lifecycle-health artifact schema version: {schema_version}")
    report_hash = payload.pop("report_sha256", None)
    if not isinstance(report_hash, str) or not report_hash:
        raise ValueError("lifecycle-health artifact hash is missing")
    if _hash_payload(payload) != report_hash:
        raise ValueError("lifecycle-health artifact hash does not match its payload")
    payload["report_sha256"] = report_hash
    return PaperLifecycleHealthArtifact(payload=payload, report_sha256=report_hash)


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


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
