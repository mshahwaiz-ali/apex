"""Verify persisted lifecycle-health artifacts against scheduler source evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from apex.application.paper_lifecycle_health_io import (
    PaperLifecycleHealthArtifact,
    load_and_verify_paper_lifecycle_health_artifact,
)

__all__ = [
    "PaperLifecycleHealthSourceStatus",
    "PaperLifecycleHealthSourceVerification",
    "paper_lifecycle_health_source_verification_payload",
    "verify_paper_lifecycle_health_artifact_source",
]


class PaperLifecycleHealthSourceStatus(StrEnum):
    """Outcome of checking an artifact against its declared scheduler evidence."""

    VERIFIED = "verified"
    SOURCE_LOG_CHANGED = "source_log_changed"
    SOURCE_RECORD_INVALID = "source_record_invalid"


@dataclass(frozen=True, slots=True)
class PaperLifecycleHealthSourceVerification:
    """Deterministic result of lifecycle-health source provenance verification."""

    status: PaperLifecycleHealthSourceStatus
    artifact_path: str
    source_log_path: str
    run_id: str
    market_type: str
    source_line_number: int
    artifact_sha256: str
    expected_source_record_sha256: str
    observed_source_record_sha256: str | None
    expected_source_log_sha256: str
    observed_source_log_sha256: str
    expected_analytics_sha256: str
    observed_analytics_sha256: str | None
    log_name_matches: bool
    source_record_matches: bool
    source_log_matches: bool
    analytics_matches: bool
    identity_matches: bool
    execution_authorized: bool
    reasons: tuple[str, ...]


def verify_paper_lifecycle_health_artifact_source(
    artifact_path: Path,
    source_log_path: Path,
) -> PaperLifecycleHealthSourceVerification:
    """Verify an artifact and its declared source record against a scheduler log."""

    artifact = load_and_verify_paper_lifecycle_health_artifact(artifact_path)
    source = _source_payload(artifact)
    raw_bytes = source_log_path.read_bytes()
    observed_source_log_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    expected_source_log_sha256 = _required_string(source, "source_log_sha256")
    expected_source_record_sha256 = _required_string(source, "source_record_sha256")
    expected_analytics_sha256 = _required_string(source, "analytics_sha256")
    source_line_number = _required_positive_int(source, "source_line_number")
    run_id = _required_string(source, "run_id")
    market_type = _required_string(source, "market_type")
    expected_log_name = _required_string(source, "log_name")

    log_name_matches = source_log_path.name == expected_log_name
    source_log_matches = observed_source_log_sha256 == expected_source_log_sha256
    observed_record, observed_record_error = _record_at_line(raw_bytes, source_line_number)
    observed_source_record_sha256 = (
        _hash_json_value(observed_record) if observed_record is not None else None
    )
    observed_analytics = (
        observed_record.get("lifecycle_analytics") if observed_record is not None else None
    )
    observed_analytics_sha256 = (
        _hash_json_value(observed_analytics) if isinstance(observed_analytics, dict) else None
    )
    source_record_matches = observed_source_record_sha256 == expected_source_record_sha256
    analytics_matches = observed_analytics_sha256 == expected_analytics_sha256
    identity_matches = (
        observed_record is not None
        and str(observed_record.get("run_id", "")).strip() == run_id
        and str(observed_record.get("market_type", "")).strip().lower() == market_type.lower()
    )

    reasons: list[str] = []
    if not log_name_matches:
        reasons.append("source_log_name_mismatch")
    if observed_record_error is not None:
        reasons.append(observed_record_error)
    if not source_record_matches:
        reasons.append("source_record_hash_mismatch")
    if not analytics_matches:
        reasons.append("analytics_hash_mismatch")
    if not identity_matches:
        reasons.append("source_identity_mismatch")
    if not source_log_matches:
        reasons.append("source_log_hash_mismatch")

    if (
        log_name_matches
        and source_record_matches
        and analytics_matches
        and identity_matches
        and source_log_matches
    ):
        status = PaperLifecycleHealthSourceStatus.VERIFIED
    elif source_record_matches and analytics_matches and identity_matches:
        status = PaperLifecycleHealthSourceStatus.SOURCE_LOG_CHANGED
    else:
        status = PaperLifecycleHealthSourceStatus.SOURCE_RECORD_INVALID

    execution_authorized = artifact.payload.get("execution_authorized") is True
    if execution_authorized:
        reasons.append("artifact_execution_authorization_forbidden")
        status = PaperLifecycleHealthSourceStatus.SOURCE_RECORD_INVALID

    return PaperLifecycleHealthSourceVerification(
        status=status,
        artifact_path=str(artifact_path),
        source_log_path=str(source_log_path),
        run_id=run_id,
        market_type=market_type,
        source_line_number=source_line_number,
        artifact_sha256=artifact.report_sha256,
        expected_source_record_sha256=expected_source_record_sha256,
        observed_source_record_sha256=observed_source_record_sha256,
        expected_source_log_sha256=expected_source_log_sha256,
        observed_source_log_sha256=observed_source_log_sha256,
        expected_analytics_sha256=expected_analytics_sha256,
        observed_analytics_sha256=observed_analytics_sha256,
        log_name_matches=log_name_matches,
        source_record_matches=source_record_matches,
        source_log_matches=source_log_matches,
        analytics_matches=analytics_matches,
        identity_matches=identity_matches,
        execution_authorized=execution_authorized,
        reasons=tuple(reasons),
    )


def paper_lifecycle_health_source_verification_payload(
    verification: PaperLifecycleHealthSourceVerification,
) -> dict[str, Any]:
    """Return a stable JSON-ready verification payload."""

    payload = asdict(verification)
    payload["status"] = verification.status.value
    payload["reasons"] = list(verification.reasons)
    return payload


def _source_payload(artifact: PaperLifecycleHealthArtifact) -> dict[str, Any]:
    value = artifact.payload.get("source")
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("lifecycle-health artifact source must be a JSON object")
    return cast(dict[str, Any], dict(value))


def _required_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"lifecycle-health artifact source {field_name} is missing")
    return value.strip()


def _required_positive_int(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"lifecycle-health artifact source {field_name} must be positive")
    return value


def _record_at_line(
    raw_bytes: bytes,
    line_number: int,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        raw_line = raw_bytes.decode("utf-8").splitlines()[line_number - 1]
    except UnicodeDecodeError:
        return None, "source_log_not_utf8"
    except IndexError:
        return None, "source_line_missing"
    line = raw_line.strip()
    if not line:
        return None, "source_line_empty"
    try:
        value: object = json.loads(line)
    except json.JSONDecodeError:
        return None, "source_line_invalid_json"
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        return None, "source_line_not_object"
    return cast(dict[str, Any], dict(value)), None


def _hash_json_value(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
