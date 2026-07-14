"""JSON persistence for frozen spot baseline reports."""

from __future__ import annotations

import json
from pathlib import Path

from apex.spot_baseline.contracts import SpotBaselineReport
from apex.spot_baseline.evaluation import spot_baseline_report_to_payload

SPOT_BASELINE_REPORT_SCHEMA_VERSION = 1


def write_spot_baseline_report(
    path: str | Path,
    report: SpotBaselineReport,
) -> None:
    """Write one deterministic report payload."""
    payload = spot_baseline_report_to_payload(report)
    Path(path).write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def load_spot_baseline_report_payload(path: str | Path) -> dict[str, object]:
    """Load and minimally validate a report payload."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("spot baseline report payload must be an object")
    if payload.get("schema_version") != SPOT_BASELINE_REPORT_SCHEMA_VERSION:
        raise ValueError("unsupported spot baseline report schema version")
    return payload
