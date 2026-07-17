"""Tests for canonical evidence bundle resolution."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apex.validation.evidence_bundle import EvidenceBundleStatus, load_evidence_bundle

DIMENSIONS = {
    "strategy": "trend_pullback",
    "symbol": "BTC/USDT",
    "direction": "long",
    "risk_mode": "STANDARD",
    "market_regime": "trend",
    "score_band": "75_84",
}


def _write_reports(tmp_path: Path, *, forward_source: str = "historical-validation") -> tuple[Path, Path]:
    historical_path = tmp_path / "historical.json"
    forward_path = tmp_path / "forward.json"
    historical = {
        "schema_version": 1,
        "report_id": "historical-validation",
        "generated_at": "2026-07-15T00:00:00+00:00",
        "campaign_id": "campaign",
        "results": [
            {
                "dimensions": DIMENSIONS,
                "status": "PASSED_VALIDATION",
                "out_of_sample_sample_size": 100,
                "evidence_stable": True,
                "promoted_evidence_quality": "VALIDATED_OUT_OF_SAMPLE",
                "rejection_reasons": [],
                "warnings": [],
            }
        ],
    }
    forward = {
        "schema_version": 1,
        "report_id": "forward-validation",
        "generated_at": "2026-07-15T01:00:00+00:00",
        "campaign_id": "campaign",
        "source_validation_report_id": forward_source,
        "results": [
            {
                "dimensions": DIMENSIONS,
                "status": "PASSED_FORWARD_PAPER",
                "forward_sample_size": 30,
                "forward_win_rate": 0.6,
                "forward_expectancy": 0.3,
                "forward_profit_factor": 1.4,
                "expectancy_degradation": 0.2,
                "promoted_evidence_quality": "VALIDATED_FORWARD_PAPER",
                "rejection_reasons": [],
            }
        ],
    }
    historical_path.write_text(json.dumps(historical), encoding="utf-8")
    forward_path.write_text(json.dumps(forward), encoding="utf-8")
    return historical_path, forward_path


def test_resolves_complete_protocol_compatible_bundle(tmp_path: Path) -> None:
    historical, forward = _write_reports(tmp_path)

    bundle = load_evidence_bundle(
        historical_validation_path=historical,
        forward_validation_path=forward,
        dimensions=DIMENSIONS,
        as_of=datetime(2026, 7, 16, tzinfo=UTC),
    )

    assert bundle.status is EvidenceBundleStatus.COMPLETE
    assert bundle.historical is not None
    assert bundle.forward is not None
    assert bundle.historical.status.value == "PASSED_VALIDATION"
    assert bundle.forward.status.value == "PASSED_VALIDATION"
    assert bundle.forward.forward_profile is not None
    assert bundle.forward.forward_profile.sample_size == 30


def test_legacy_scanner_dimension_matches_canonical_segment(tmp_path: Path) -> None:
    historical, forward = _write_reports(tmp_path)

    for path in (historical, forward):
        document = json.loads(path.read_text(encoding="utf-8"))
        document["results"][0]["dimensions"]["scanner_type"] = "gainers"
        path.write_text(json.dumps(document), encoding="utf-8")

    bundle = load_evidence_bundle(
        historical_validation_path=historical,
        forward_validation_path=forward,
        dimensions=DIMENSIONS,
        as_of=datetime(2026, 7, 16, tzinfo=UTC),
    )

    assert bundle.status is EvidenceBundleStatus.COMPLETE
    assert dict(bundle.dimensions) == DIMENSIONS
    assert bundle.historical is not None
    assert dict(bundle.historical.dimensions) == DIMENSIONS
    assert bundle.forward is not None
    assert dict(bundle.forward.dimensions) == DIMENSIONS


def test_bundle_identity_is_independent_of_as_of_time(tmp_path: Path) -> None:
    historical, forward = _write_reports(tmp_path)

    first = load_evidence_bundle(
        historical_validation_path=historical,
        forward_validation_path=forward,
        dimensions=DIMENSIONS,
        as_of=datetime(2026, 7, 16, tzinfo=UTC),
    )
    second = load_evidence_bundle(
        historical_validation_path=historical,
        forward_validation_path=forward,
        dimensions=DIMENSIONS,
        as_of=datetime(2026, 7, 17, tzinfo=UTC),
    )

    assert first.bundle_id == second.bundle_id


def test_marks_stale_chain(tmp_path: Path) -> None:
    historical, forward = _write_reports(tmp_path)

    bundle = load_evidence_bundle(
        historical_validation_path=historical,
        forward_validation_path=forward,
        dimensions=DIMENSIONS,
        as_of=datetime(2026, 8, 15, tzinfo=UTC),
        maximum_age=timedelta(days=7),
    )

    assert bundle.status is EvidenceBundleStatus.STALE
    assert "REPORT_STALE" in bundle.to_payload()["reasons"]


def test_detects_missing_segment_and_lineage_mismatch(tmp_path: Path) -> None:
    historical, forward = _write_reports(tmp_path, forward_source="wrong-report")
    missing = {**DIMENSIONS, "symbol": "ETH/USDT"}

    bundle = load_evidence_bundle(
        historical_validation_path=historical,
        forward_validation_path=forward,
        dimensions=missing,
        as_of=datetime(2026, 7, 16, tzinfo=UTC),
    )

    assert bundle.status is EvidenceBundleStatus.LINEAGE_MISMATCH
    reasons = bundle.to_payload()["reasons"]
    assert "REPORT_LINEAGE_MISMATCH" in reasons
    assert "HISTORICAL_SEGMENT_MISSING" in reasons
    assert "FORWARD_SEGMENT_MISSING" in reasons
