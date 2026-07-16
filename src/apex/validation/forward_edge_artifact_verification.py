"""Verify sealed forward-edge artifacts against historical-validation evidence."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from apex.validation.forward_edge_artifact import load_and_verify_forward_edge_artifact

__all__ = [
    "ForwardEdgeArtifactSourceStatus",
    "ForwardEdgeArtifactSourceVerification",
    "forward_edge_artifact_source_verification_payload",
    "verify_forward_edge_artifact_source",
]


class ForwardEdgeArtifactSourceStatus(StrEnum):
    """Outcome of checking a sealed artifact against historical source evidence."""

    VERIFIED = "verified"
    SOURCE_CHANGED = "source_changed"


@dataclass(frozen=True, slots=True)
class ForwardEdgeArtifactSourceVerification:
    """Deterministic source-verification result for one sealed artifact."""

    status: ForwardEdgeArtifactSourceStatus
    artifact_path: str
    historical_validation_path: str
    historical_validation_name_matches: bool
    expected_historical_validation_sha256: str
    observed_historical_validation_sha256: str
    source_matches: bool
    execution_authorized: bool
    reasons: tuple[str, ...]


def verify_forward_edge_artifact_source(
    artifact_path: Path,
    historical_validation_path: Path,
) -> ForwardEdgeArtifactSourceVerification:
    """Verify a sealed artifact against the supplied historical-validation file."""

    artifact = load_and_verify_forward_edge_artifact(artifact_path)
    source = artifact["source"]
    expected_name = str(source["historical_validation_name"])
    expected_hash = str(source["historical_validation_sha256"])
    observed_hash = hashlib.sha256(historical_validation_path.read_bytes()).hexdigest()
    name_matches = historical_validation_path.name == expected_name
    source_matches = observed_hash == expected_hash
    execution_authorized = artifact.get("execution_authorized") is True

    reasons: list[str] = []
    if not name_matches:
        reasons.append("historical_validation_name_mismatch")
    if not source_matches:
        reasons.append("historical_validation_hash_mismatch")
    if execution_authorized:
        reasons.append("artifact_execution_authorization_forbidden")

    status = (
        ForwardEdgeArtifactSourceStatus.VERIFIED
        if name_matches and source_matches and not execution_authorized
        else ForwardEdgeArtifactSourceStatus.SOURCE_CHANGED
    )
    return ForwardEdgeArtifactSourceVerification(
        status=status,
        artifact_path=str(artifact_path),
        historical_validation_path=str(historical_validation_path),
        historical_validation_name_matches=name_matches,
        expected_historical_validation_sha256=expected_hash,
        observed_historical_validation_sha256=observed_hash,
        source_matches=source_matches,
        execution_authorized=execution_authorized,
        reasons=tuple(reasons),
    )


def forward_edge_artifact_source_verification_payload(
    verification: ForwardEdgeArtifactSourceVerification,
) -> dict[str, Any]:
    """Return a stable JSON-ready verification payload."""

    payload = asdict(verification)
    payload["status"] = verification.status.value
    payload["reasons"] = list(verification.reasons)
    return payload
