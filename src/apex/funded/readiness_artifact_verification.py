"""Verify sealed funded-readiness artifacts against exact source files."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from apex.funded.readiness_artifact import load_and_verify_funded_readiness_artifact

__all__ = [
    "FundedReadinessArtifactSourceStatus",
    "FundedReadinessArtifactSourceVerification",
    "funded_readiness_artifact_source_verification_payload",
    "verify_funded_readiness_artifact_sources",
]


class FundedReadinessArtifactSourceStatus(StrEnum):
    """Outcome of checking all sealed funded-readiness source files."""

    VERIFIED = "verified"
    SOURCE_CHANGED = "source_changed"


@dataclass(frozen=True, slots=True)
class FundedReadinessArtifactSourceVerification:
    """Deterministic verification result for one funded-readiness artifact."""

    status: FundedReadinessArtifactSourceStatus
    artifact_path: str
    source_matches: Mapping[str, bool]
    source_name_matches: Mapping[str, bool]
    execution_authorized: bool
    reasons: tuple[str, ...]


def verify_funded_readiness_artifact_sources(
    artifact_path: Path,
    *,
    input_path: Path,
    report_path: Path,
) -> FundedReadinessArtifactSourceVerification:
    """Verify one artifact against the supplied input and report files."""

    artifact = load_and_verify_funded_readiness_artifact(artifact_path)
    supplied = {
        "input": input_path,
        "report": report_path,
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
        FundedReadinessArtifactSourceStatus.VERIFIED
        if all(source_matches.values())
        and all(source_name_matches.values())
        and not execution_authorized
        else FundedReadinessArtifactSourceStatus.SOURCE_CHANGED
    )
    return FundedReadinessArtifactSourceVerification(
        status=status,
        artifact_path=str(artifact_path),
        source_matches=source_matches,
        source_name_matches=source_name_matches,
        execution_authorized=execution_authorized,
        reasons=tuple(reasons),
    )


def funded_readiness_artifact_source_verification_payload(
    verification: FundedReadinessArtifactSourceVerification,
) -> dict[str, Any]:
    """Return a stable JSON-ready verification payload."""

    payload = asdict(verification)
    payload["status"] = verification.status.value
    payload["source_matches"] = dict(verification.source_matches)
    payload["source_name_matches"] = dict(verification.source_name_matches)
    payload["reasons"] = list(verification.reasons)
    return payload
