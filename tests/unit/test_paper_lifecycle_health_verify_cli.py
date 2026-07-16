from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from typer.testing import CliRunner

from apex.application.paper_lifecycle_health_verification import (
    PaperLifecycleHealthSourceStatus,
    PaperLifecycleHealthSourceVerification,
)
from apex.cli_commands import paper_lifecycle_health_verify as verify_cli

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    paper_app = typer.Typer(no_args_is_help=True)
    verify_cli.register_paper_lifecycle_health_verify_command(paper_app)
    app.add_typer(paper_app, name="paper")
    return app


def _verification(
    status: PaperLifecycleHealthSourceStatus,
) -> PaperLifecycleHealthSourceVerification:
    verified = status is PaperLifecycleHealthSourceStatus.VERIFIED
    source_record_matches = status is not PaperLifecycleHealthSourceStatus.SOURCE_RECORD_INVALID
    return PaperLifecycleHealthSourceVerification(
        status=status,
        artifact_path="health.json",
        source_log_path="pipeline-futures.jsonl",
        run_id="run-1",
        market_type="futures",
        source_line_number=1,
        artifact_sha256="a" * 64,
        expected_source_record_sha256="b" * 64,
        observed_source_record_sha256="b" * 64 if source_record_matches else "c" * 64,
        expected_source_log_sha256="d" * 64,
        observed_source_log_sha256="d" * 64 if verified else "e" * 64,
        expected_analytics_sha256="f" * 64,
        observed_analytics_sha256="f" * 64 if source_record_matches else "0" * 64,
        log_name_matches=True,
        source_record_matches=source_record_matches,
        source_log_matches=verified,
        analytics_matches=source_record_matches,
        identity_matches=source_record_matches,
        execution_authorized=False,
        reasons=() if verified else ("source_log_hash_mismatch",),
    )


def _files(tmp_path: Path) -> tuple[Path, Path]:
    artifact = tmp_path / "health.json"
    source_log = tmp_path / "pipeline-futures.jsonl"
    artifact.write_text("{}\n", encoding="utf-8")
    source_log.write_text("{}\n", encoding="utf-8")
    return artifact, source_log


def test_verify_command_is_registered() -> None:
    result = runner.invoke(_app(), ["paper", "--help"])

    assert result.exit_code == 0
    assert "lifecycle-health-verify" in result.output


def test_verify_command_emits_json_for_verified_evidence(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    artifact, source_log = _files(tmp_path)
    monkeypatch.setattr(
        verify_cli,
        "verify_paper_lifecycle_health_artifact_source",
        lambda artifact_path, source_log_path: _verification(
            PaperLifecycleHealthSourceStatus.VERIFIED
        ),
    )

    result = runner.invoke(
        _app(),
        [
            "paper",
            "lifecycle-health-verify",
            "--artifact",
            str(artifact),
            "--source-log",
            str(source_log),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "verified"
    assert payload["source_record_matches"] is True
    assert payload["source_log_matches"] is True


def test_verify_command_exits_two_for_changed_source_log(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    artifact, source_log = _files(tmp_path)
    monkeypatch.setattr(
        verify_cli,
        "verify_paper_lifecycle_health_artifact_source",
        lambda artifact_path, source_log_path: _verification(
            PaperLifecycleHealthSourceStatus.SOURCE_LOG_CHANGED
        ),
    )

    result = runner.invoke(
        _app(),
        [
            "paper",
            "lifecycle-health-verify",
            "--artifact",
            str(artifact),
            "--source-log",
            str(source_log),
        ],
    )

    assert result.exit_code == 2
    assert "status=source_log_changed" in result.output
    assert "source_record_matches=true" in result.output
    assert "source_log_matches=false" in result.output


def test_verify_command_exits_two_for_invalid_source_record(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    artifact, source_log = _files(tmp_path)
    monkeypatch.setattr(
        verify_cli,
        "verify_paper_lifecycle_health_artifact_source",
        lambda artifact_path, source_log_path: _verification(
            PaperLifecycleHealthSourceStatus.SOURCE_RECORD_INVALID
        ),
    )

    result = runner.invoke(
        _app(),
        [
            "paper",
            "lifecycle-health-verify",
            "--artifact",
            str(artifact),
            "--source-log",
            str(source_log),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["status"] == "source_record_invalid"
    assert payload["source_record_matches"] is False


def test_invalid_output_fails_before_verification(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    artifact, source_log = _files(tmp_path)
    called = False

    def fail_if_called(artifact_path: Path, source_log_path: Path) -> object:
        nonlocal called
        called = True
        raise AssertionError("verification should not run")

    monkeypatch.setattr(
        verify_cli,
        "verify_paper_lifecycle_health_artifact_source",
        fail_if_called,
    )

    result = runner.invoke(
        _app(),
        [
            "paper",
            "lifecycle-health-verify",
            "--artifact",
            str(artifact),
            "--source-log",
            str(source_log),
            "--output",
            "invalid",
        ],
    )

    assert result.exit_code != 0
    assert "output must be text or json" in result.output
    assert called is False
