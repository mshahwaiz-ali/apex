"""Atomic JSON persistence for frozen V2 baseline reports."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from apex.baseline.contracts import BaselineEvaluationReport
from apex.baseline.evaluation import baseline_report_to_payload

BASELINE_REPORT_SCHEMA_VERSION = 1


def write_baseline_report(
    path: str | Path,
    report: BaselineEvaluationReport,
    *,
    force: bool = False,
) -> Path:
    """Atomically write a complete baseline report envelope."""

    target = Path(path)
    if target.exists() and not force:
        raise ValueError(f"baseline report already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = baseline_report_to_payload(report)
    payload["schema_version"] = BASELINE_REPORT_SCHEMA_VERSION
    encoded = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return target


def load_baseline_report_payload(path: str | Path) -> dict[str, object]:
    """Load and minimally validate a persisted baseline report payload."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("baseline report must contain a JSON object")
    if payload.get("schema_version") != BASELINE_REPORT_SCHEMA_VERSION:
        raise ValueError("unsupported baseline report schema version")
    if not isinstance(payload.get("report_id"), str) or not payload["report_id"]:
        raise ValueError("baseline report id is required")
    return payload
