"""Tests for sealed forward-edge evidence artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apex.validation.forward_edge_artifact import (
    build_forward_edge_artifact,
    load_and_verify_forward_edge_artifact,
    write_forward_edge_artifact,
)


def _report() -> dict[str, object]:
    return {
        "schema_version": 1,
        "report_id": "forward-edge-example",
        "generated_at": "2026-07-16T12:00:00+00:00",
        "campaign_id": "campaign-1",
        "source_validation_report_id": "historical-validation-1",
        "policy": {
            "minimum_closed_trades": 30,
            "minimum_expectancy": 0.0,
            "minimum_profit_factor": 1.0,
            "maximum_expectancy_degradation": 0.5,
        },
        "segment_count": 0,
        "validated_forward_paper_count": 0,
        "results": [],
        "warnings": [],
    }


def _historical(path: Path, *, suffix: str = "") -> Path:
    payload = {
        "schema_version": 1,
        "report_id": "historical-validation-1",
        "campaign_id": "campaign-1",
        "results": [],
        "suffix": suffix,
    }
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_artifact_is_deterministic_and_path_independent(tmp_path: Path) -> None:
    left = _historical(tmp_path / "left.json")
    right_dir = tmp_path / "nested"
    right_dir.mkdir()
    right = right_dir / "left.json"
    right.write_bytes(left.read_bytes())

    first = build_forward_edge_artifact(_report(), historical_validation_path=left)
    second = build_forward_edge_artifact(_report(), historical_validation_path=right)

    assert first == second
    assert first["source"]["historical_validation_name"] == "left.json"
    assert "historical_validation_path" not in first["source"]
    assert first["execution_authorized"] is False


def test_source_hash_changes_when_historical_evidence_changes(tmp_path: Path) -> None:
    source = _historical(tmp_path / "historical.json")
    first = build_forward_edge_artifact(_report(), historical_validation_path=source)
    _historical(source, suffix="changed")
    second = build_forward_edge_artifact(_report(), historical_validation_path=source)

    assert first["source"]["historical_validation_sha256"] != second["source"][
        "historical_validation_sha256"
    ]
    assert first["artifact_sha256"] != second["artifact_sha256"]


def test_artifact_round_trip_and_overwrite_protection(tmp_path: Path) -> None:
    source = _historical(tmp_path / "historical.json")
    artifact = build_forward_edge_artifact(_report(), historical_validation_path=source)
    output = tmp_path / "sealed.json"

    write_forward_edge_artifact(output, artifact)
    assert load_and_verify_forward_edge_artifact(output) == artifact

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_forward_edge_artifact(output, artifact)

    write_forward_edge_artifact(output, artifact, force=True)
    assert load_and_verify_forward_edge_artifact(output) == artifact


def test_artifact_tampering_is_rejected(tmp_path: Path) -> None:
    source = _historical(tmp_path / "historical.json")
    artifact = build_forward_edge_artifact(_report(), historical_validation_path=source)
    output = tmp_path / "sealed.json"
    write_forward_edge_artifact(output, artifact)

    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["forward_edge_report"]["validated_forward_paper_count"] = 1
    output.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="hash does not match"):
        load_and_verify_forward_edge_artifact(output)


def test_execution_authorization_is_rejected(tmp_path: Path) -> None:
    source = _historical(tmp_path / "historical.json")
    artifact = build_forward_edge_artifact(_report(), historical_validation_path=source)
    artifact["execution_authorized"] = True

    with pytest.raises(ValueError, match="cannot authorize execution"):
        write_forward_edge_artifact(tmp_path / "sealed.json", artifact)
