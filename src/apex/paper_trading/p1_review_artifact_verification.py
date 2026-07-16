"""Verify sealed P1 review artifacts against exact source evidence files."""

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
    VERIFIED = "verified"
    SOURCE_CHANGED = "source_changed"


@dataclass(frozen=True, slots=True)
class P1ReviewArtifactSourceVerification:
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
    artifact = load_and_verify_p1_review_artifact(artifact_path)
    supplied = {
        "review_report": review_report_path,
        "