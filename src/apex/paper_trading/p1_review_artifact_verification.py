"""Verify sealed forward-validation review artifacts against exact source evidence files."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from apex.paper_trading.p1_review_artifact import load_and_verify_p1_review_artifact

__all__ = [
    "P1ReviewArtifactSourceStatus",
    "P1ReviewArtifactSourceVerification",
    "p1_review_artifact_source_verification_payload",
    "verify_p1_review_artifact_sources",
]


class P1ReviewArtifactSourceStatus(StrEnum):
    """Outcome of checking all sealed forward-validation review source files."""

    VERIFIED = "verified"
    SOURCE_CHANGED = "source_changed"


@dataclass(frozen=True, slots=True)
class P1ReviewArtifactSourceVerification:
    """Deterministic source-verification result for one sealed forward-validation review."""

    status: P1ReviewArtifactSourceStatus
    artifact_path: str
    source_matches: Mapping[str, bool]
    source_name_matches: Mapping[str, bool]
    execution_authorized: bool
    reasons: tuple[str, ...]


def verify_p1_review_artifact_sources(
    artifact_path: Path,
    *,
    review_report_path: Path,
    historical_profile_path: Path,
    forward_profile_path: Path,
    daily_report_path: Path,
    paper_store_path: Path,
) -> P1ReviewArtifactSourceVerification:
    """Verify a sealed forward-validation review artifact against all supplied source files."""

    artifact = load_and_verify_p1_review_artifact(artifact_path)
    supplied = {
        "review_report": review_report_path,
        "historical_profile": historical_profile_path,
        "forward_profile": forward_profile_path,
        "daily_report": daily_report_path,
        "paper_store": paper_store_path,
    }
    sources = artifact["sources"]
    source_matches: dict[str, bool] = {}
    source_name_matches: dict[str, bool] = {}
    reasons: list[str] = []

    for label in sorted(supplied):
        path = supplied[label]
        expected = sources[label]
        observed_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        hash_matches = observed_hash == str(expected["sha256"])
        name_matches = path.name == str(expected["name"])
        source_matches[label] = hash_matches
        source_name_matches[label] = name_matches
        if not name_matches:
            reasons.append(f"{label}_name_mismatch")
        if not hash_matches:
            reasons.append(f"{label}_hash_mismatch")

    execution_authorized = artifact.get("execution_authorized") is True
    if execution_authorized:
        reasons.append("artifact_execution_authorization_forbidden")

    status = (
        P1ReviewArtifactSourceStatus.VERIFIED
        if all(source_matches.values())
        and all(source_name_matches.values())
        and not execution_authorized
        else P1ReviewArtifactSourceStatus.SOURCE_CHANGED
    )
    return P1ReviewArtifactSourceVerification(
        status=status,
        artifact_path=str(artifact_path),
        source_matches=source_matches,
        source_name_matches=source_name_matches,
        execution_authorized=execution_authorized,
        reasons=tuple(reasons),
    )


def p1_review_artifact_source_verification_payload(
    verification: P1ReviewArtifactSourceVerification,
) -> dict[str, Any]:
    """Return a stable JSON-ready verification payload."""

    payload = asdict(verification)
    payload["status"] = verification.status.value
    payload["source_matches"] = dict(verification.source_matches)
    payload["source_name_matches"] = dict(verification.source_name_matches)
    payload["reasons"] = list(verification.reasons)
    return payload
