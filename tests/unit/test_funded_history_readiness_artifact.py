from __future__ import annotations

import json
from pathlib import Path

import pytest

from apex.funded.history_readiness_artifact import (
    build_funded_history_readiness_artifact,
    load_and_verify_funded_history_readiness_artifact,
    write_funded_history_readiness_artifact,
)


def _write_input(path: Path, *, provider: str = "Example Funded") -> None:
    path.write_text(
        json.dumps({"provider_limits": {"provider_name": provider}}, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_history(path: Path, *, ready: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-07-16T12:00:00+00:00",
                "ready_for_funded_review": ready,
                "reasons": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_report(
    path: Path,
    *,
    provider: str = "Example Funded",
    ready: bool = True,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-07-16T12:00:00+00:00",
                "ready": ready,
                "provider_name": provider,
                "reasons": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    input_path = tmp_path / "funded-input.json"
    history_path = tmp_path / "history-review.json"
    report_path = tmp_path / "funded-report.json"
    _write_input(input_path)
    _write_history(history_path)
    _write_report(report_path)
    return input_path, history_path, report_path


def test_artifact_is_deterministic_and_path_independent(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    left_input, left_history, left_report = _sources(left)
    right_input, right_history, right_report = _sources(right)

    first = build_funded_history_readiness_artifact(
        input_path=left_input,
        history_review_path=left_history,
        report_path=left_report,
    )
    second = build_funded_history_readiness_artifact(
        input_path=right_input,
        history_review_path=right_history,
        report_path=right_report,
    )

    assert first == second
    assert first["provider_name"] == "Example Funded"
    assert first["ready"] is True
    assert first["history_ready_for_funded_review"] is True
    assert first["execution_authorized"] is False
    assert len(first["artifact_sha256"]) == 64


def test_artifact_rejects_provider_and_history_inconsistency(tmp_path: Path) -> None:
    input_path, history_path, report_path = _sources(tmp_path)
    _write_report(report_path, provider="Different Provider")
    with pytest.raises(ValueError, match="provider identity mismatch"):
        build_funded_history_readiness_artifact(
            input_path=input_path,
            history_review_path=history_path,
            report_path=report_path,
        )

    _write_report(report_path, ready=True)
    _write_history(history_path, ready=False)
    with pytest.raises(ValueError, match="cannot use non-ready aggregate history"):
        build_funded_history_readiness_artifact(
            input_path=input_path,
            history_review_path=history_path,
            report_path=report_path,
        )


def test_artifact_round_trip_and_overwrite_protection(tmp_path: Path) -> None:
    input_path, history_path, report_path = _sources(tmp_path)
    artifact = build_funded_history_readiness_artifact(
        input_path=input_path,
        history_review_path=history_path,
        report_path=report_path,
    )
    output = tmp_path / "sealed.json"

    write_funded_history_readiness_artifact(output, artifact)
    assert load_and_verify_funded_history_readiness_artifact(output) == artifact

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_funded_history_readiness_artifact(output, artifact)

    write_funded_history_readiness_artifact(output, artifact, force=True)
    assert load_and_verify_funded_history_readiness_artifact(output) == artifact


def test_history_change_changes_artifact_identity(tmp_path: Path) -> None:
    input_path, history_path, report_path = _sources(tmp_path)
    first = build_funded_history_readiness_artifact(
        input_path=input_path,
        history_review_path=history_path,
        report_path=report_path,
    )
    _write_history(history_path, ready=False)
    _write_report(report_path, ready=False)
    second = build_funded_history_readiness_artifact(
        input_path=input_path,
        history_review_path=history_path,
        report_path=report_path,
    )

    assert first["sources"]["history_review"]["sha256"] != second["sources"]["history_review"]["sha256"]
    assert first["artifact_sha256"] != second["artifact_sha256"]


def test_tampering_and_execution_authorization_are_rejected(tmp_path: Path) -> None:
    input_path, history_path, report_path = _sources(tmp_path)
    artifact = build_funded_history_readiness_artifact(
        input_path=input_path,
        history_review_path=history_path,
        report_path=report_path,
    )
    output = tmp_path / "sealed.json"
    write_funded_history_readiness_artifact(output, artifact)

    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["ready"] = False
    output.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash does not match"):
        load_and_verify_funded_history_readiness_artifact(output)

    artifact["execution_authorized"] = True
    with pytest.raises(ValueError, match="cannot authorize execution"):
        write_funded_history_readiness_artifact(tmp_path / "forbidden.json", artifact)
