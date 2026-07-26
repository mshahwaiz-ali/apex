"""Stable identity for the implemented quality-recovery methodology."""

from __future__ import annotations

import hashlib
from pathlib import Path

METHODOLOGY_AUTHORITY_PATH = "docs/apex_quality_recovery_audit.md"
METHODOLOGY_VERSION = "quality-recovery-v1"


def methodology_identity_payload() -> dict[str, str | None]:
    """Return the versioned authority identity without assuming docs ship in wheels."""

    relative = Path(METHODOLOGY_AUTHORITY_PATH)
    candidates = (Path.cwd() / relative, Path(__file__).resolve().parents[3] / relative)
    authority = next((path for path in candidates if path.is_file()), None)
    digest = None
    if authority is not None:
        digest = hashlib.sha256(authority.read_bytes()).hexdigest()
    return {
        "authority_path": METHODOLOGY_AUTHORITY_PATH,
        "version": METHODOLOGY_VERSION,
        "authority_sha256": digest,
        "authority_status": "available" if digest is not None else "not_packaged",
    }


__all__ = [
    "METHODOLOGY_AUTHORITY_PATH",
    "METHODOLOGY_VERSION",
    "methodology_identity_payload",
]
