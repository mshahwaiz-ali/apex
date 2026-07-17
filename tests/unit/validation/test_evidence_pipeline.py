"""Tests for atomic evidence pipeline orchestration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from apex.validation import evidence_pipeline

DIMENSIONS = {
    "strategy": "trend_pullback",
    "symbol": "BTC/USDT",
    "direction": "long",
    "risk_mode": "STANDARD",
    "market_regime": "trend",
    "score_band": "75_84",
}


def _install_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    def write_json(path: Path, payload: dict[str, Any], **_: object) -> None:
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        evidence_pipeline,
        "build_historical_futures_edge_report",
        lambda **_: {"schema_version": 1, "report_id": "edge", "campaign_id": "campaign"},
    )
    monkeypatch.setattr(evidence_pipeline, "write_historical_edge_report", write_json)
    monkeypatch.setattr(
        evidence_pipeline,
        "build_historical_futures_edge_validation_report",
        lambda **_: {
            "schema_version": 1,
            "report_id": "historical-validation",
            "campaign_id": "campaign",
            "results": [],
        },
    )
    monkeypatch.setattr(
        evidence_pipeline,
        "write_historical_futures_edge_validation_report",
        write_json,
    )
    monkeypatch.setattr(
        evidence_pipeline,
        "build_forward_edge_report",
        lambda **_: {
            "schema_version": 1,
            "report_id": "forward-validation",
            "campaign_id": "campaign",
            "results": [],
        },
    )
    monkeypatch.setattr(evidence_pipeline, "write_forward_edge_report", write_json)
    monkeypatch.setattr(
        evidence_pipeline,
        "load_evidence_bundle",
        lambda **_: SimpleNamespace(
            campaign_id="campaign",
            status=SimpleNamespace(value="COMPLETE"),
            to_payload=lambda: {
                "bundle_id": "bundle",
                "campaign_id": "campaign",
                "status": "COMPLETE",
            },
        ),
    )


def _sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    result = tmp_path / "result.json"
    manifest = tmp_path / "execution-manifest.json"
    paper = tmp_path / "paper.json"
    result.write_text('{"result": 1}\n', encoding="utf-8")
    manifest.write_text('{"manifest": 1}\n', encoding="utf-8")
    paper.write_text("[]\n", encoding="utf-8")
    return result, manifest, paper


def test_publishes_complete_pipeline_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fakes(monkeypatch)
    result, execution_manifest, paper = _sources(tmp_path)
    output = tmp_path / "pipeline"

    published = evidence_pipeline.run_evidence_pipeline(
        result_path=result,
        execution_manifest_path=execution_manifest,
        dimensions=DIMENSIONS,
        output_directory=output,
        generated_at=datetime(2026, 7, 15, tzinfo=UTC),
        paper_store_path=paper,
    )

    assert published.output_directory == output
    assert published.forward_validation_path == output / "forward-validation.json"
    assert (output / "historical-edge.json").is_file()
    assert (output / "historical-validation.json").is_file()
    assert (output / "forward-validation.json").is_file()
    assert (output / "evidence-bundle.json").is_file()
    manifest = json.loads((output / "pipeline-manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["includes_forward_paper"] is True
    assert manifest["bundle_status"] == "COMPLETE"
    assert not (tmp_path / ".pipeline.staging").exists()


def test_pipeline_identity_is_deterministic_for_same_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fakes(monkeypatch)
    result, execution_manifest, paper = _sources(tmp_path)

    first = evidence_pipeline.run_evidence_pipeline(
        result_path=result,
        execution_manifest_path=execution_manifest,
        dimensions=DIMENSIONS,
        output_directory=tmp_path / "first",
        generated_at=datetime(2026, 7, 15, tzinfo=UTC),
        paper_store_path=paper,
    )
    second = evidence_pipeline.run_evidence_pipeline(
        result_path=result,
        execution_manifest_path=execution_manifest,
        dimensions=DIMENSIONS,
        output_directory=tmp_path / "second",
        generated_at=datetime(2026, 7, 15, tzinfo=UTC),
        paper_store_path=paper,
    )

    assert first.pipeline_id == second.pipeline_id


def test_historical_only_pipeline_omits_forward_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fakes(monkeypatch)
    result, execution_manifest, _ = _sources(tmp_path)
    output = tmp_path / "pipeline"

    published = evidence_pipeline.run_evidence_pipeline(
        result_path=result,
        execution_manifest_path=execution_manifest,
        dimensions=DIMENSIONS,
        output_directory=output,
        generated_at=datetime(2026, 7, 15, tzinfo=UTC),
    )

    assert published.forward_validation_path is None
    assert not (output / "forward-validation.json").exists()
    manifest = json.loads((output / "pipeline-manifest.json").read_text(encoding="utf-8"))
    assert manifest["includes_forward_paper"] is False


def test_failure_preserves_existing_published_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fakes(monkeypatch)
    result, execution_manifest, _ = _sources(tmp_path)
    output = tmp_path / "pipeline"
    output.mkdir()
    marker = output / "existing.txt"
    marker.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(
        evidence_pipeline,
        "build_historical_futures_edge_validation_report",
        lambda **_: (_ for _ in ()).throw(ValueError("validation failed")),
    )

    with pytest.raises(ValueError, match="validation failed"):
        evidence_pipeline.run_evidence_pipeline(
            result_path=result,
            execution_manifest_path=execution_manifest,
            dimensions=DIMENSIONS,
            output_directory=output,
            generated_at=datetime(2026, 7, 15, tzinfo=UTC),
            force=True,
        )

    assert marker.read_text(encoding="utf-8") == "preserve"
    assert not (tmp_path / ".pipeline.staging").exists()


def test_existing_output_requires_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fakes(monkeypatch)
    result, execution_manifest, _ = _sources(tmp_path)
    output = tmp_path / "pipeline"
    output.mkdir()

    with pytest.raises(FileExistsError):
        evidence_pipeline.run_evidence_pipeline(
            result_path=result,
            execution_manifest_path=execution_manifest,
            dimensions=DIMENSIONS,
            output_directory=output,
            generated_at=datetime(2026, 7, 15, tzinfo=UTC),
        )
