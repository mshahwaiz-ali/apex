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


