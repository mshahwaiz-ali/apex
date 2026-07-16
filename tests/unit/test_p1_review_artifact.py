from __future__ import annotations

import json
from pathlib import Path

import pytest

from apex.paper_trading.p1_review_artifact import (
    build_p1_review_artifact,
    load_and_verify_p1_review_artifact,
    write_p1_review_artifact,
)


def _write_review(path: Path) -> None:
    payload = {
        "schema_version": 1,
        "generated_at": "2026-07-16T12:00:00+00:00",
        "daily_report_sha256": "a" * 64,
        "forward_validation_status": "PASSED_VALIDATION",
        "deviation": {},
        "lifecycle_audit": {},
        "sample_sufficient": True,
        "manual_execution_usable": True,
        "review_state": "FORWARD_VALIDATED",
        "production_eligible": False,
        "production_eligibility_reason": "P1 forward validation does not authorize real-money production execution.",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    import hashlib

    payload["report_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _sources(tmp_path: Path) -> dict[str, Path]:
    review = tmp_path / "review.json"
    _write_review(review)
    result = {"review_report_path": review}
    for key, name in (
        ("historical_profile_path", "historical.json"),
        ("forward_profile_path", "forward.json"),
        ("daily_report_path", "daily.json"),
        ("paper_store_path", "trades.json"),
    ):
        path = tmp_path / name
        path.write_text("{}\n", encoding="utf-8")
        result[key] = path
    return result


def test_artifact_is_deterministic_and_path_independent(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    left_sources = _sources(left)
    right_sources = _sources(right)

    first = build_p1_review_artifact(**left_sources)
    second = build_p1_review_artifact(**right_sources)

    assert first == second
    assert first["execution_authorized"] is False
    assert len(first["artifact_sha256"]) == 64


def test_artifact_round_trip_and_overwrite_protection(tmp_path: Path) -> None:
    artifact = build_p1_review_artifact(**_sources(tmp_path))
    output = tmp_path / "sealed.json"

    write_p1_review_artifact(output, artifact)
    assert load_and_verify_p1_review_artifact(output) == artifact

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_p1_review_artifact(output, artifact)


def test_source_change_changes_artifact_identity(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    first = build_p1_review_artifact(**sources)
    sources["paper_store_path"].write_text('{"changed": true}\n', encoding="utf-8")
    second = build_p1_review_artifact(**sources)

    assert first["sources"]["paper_store"]["sha256"] != second["sources"]["paper_store"]["sha256"]
    assert first["artifact_sha256"] != second["artifact_sha256"]


def test_tampering_and_execution_authorization_are_rejected(tmp_path: Path) -> None:
    artifact = build_p1_review_artifact(**_sources(tmp_path))
    output = tmp_path / "sealed.json"
    write_p1_review_artifact(output, artifact)

    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["review_state"] = "FAILED_VALIDATION"
    output.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash does not match"):
        load_and_verify_p1_review_artifact(output)

    artifact["execution_authorized"] = True
    with pytest.raises(ValueError, match="cannot authorize execution"):
        write_p1_review_artifact(tmp_path / "forbidden.json", artifact)
