from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.forward_edge_artifact_verify import (
    register_forward_edge_artifact_verify_commands,
)
from apex.validation.forward_edge_artifact import (
    build_forward_edge_artifact,
    write_forward_edge_artifact,
)
from apex.validation.forward_edge_artifact_verification import (
    ForwardEdgeArtifactSourceStatus,
    forward_edge_artifact_source_verification_payload,
    verify_forward_edge_artifact_source,
)

runner = CliRunner()


def _report() -> dict[str, object]:
    return {
        "schema_version": 1,
        "report_id": "forward-edge-example",
        "generated_at": "2026-07-16T12:00:00+00:00",
        "campaign_id": "campaign-1",
        "source_validation_report_id": "historical-validation-1",
        "policy": {},
        "segment_count": 0,
        "validated_forward_paper_count": 0,
        "results": [],
        "warnings": [],
    }


def _write_historical(path: Path, *, suffix: str = "") -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "report_id": "historical-validation-1",
                "campaign_id": "campaign-1",
                "results": [],
                "suffix": suffix,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_artifact(tmp_path: Path) -> tuple[Path, Path]:
    historical = _write_historical(tmp_path / "historical.json")
    artifact = build_forward_edge_artifact(
        _report(),
        historical_validation_path=historical,
    )
    artifact_path = tmp_path / "sealed.json"
    write_forward_edge_artifact(artifact_path, artifact)
    return artifact_path, historical


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_forward_edge_artifact_verify_commands(app)
    return app


def test_source_verification_accepts_exact_historical_evidence(tmp_path: Path) -> None:
    artifact_path, historical = _write_artifact(tmp_path)

    verification = verify_forward_edge_artifact_source(artifact_path, historical)
    payload = forward_edge_artifact_source_verification_payload(verification)

    assert verification.status is ForwardEdgeArtifactSourceStatus.VERIFIED
    assert verification.historical_validation_name_matches is True
    assert verification.source_matches is True
    assert verification.execution_authorized is False
    assert verification.reasons == ()
    assert payload["status"] == "verified"
    assert payload["reasons"] == []


def test_source_verification_rejects_changed_historical_evidence(tmp_path: Path) -> None:
    artifact_path, historical = _write_artifact(tmp_path)
    _write_historical(historical, suffix="changed")

    verification = verify_forward_edge_artifact_source(artifact_path, historical)

    assert verification.status is ForwardEdgeArtifactSourceStatus.SOURCE_CHANGED
    assert verification.historical_validation_name_matches is True
    assert verification.source_matches is False
    assert verification.reasons == ("historical_validation_hash_mismatch",)


def test_source_verification_rejects_renamed_historical_evidence(tmp_path: Path) -> None:
    artifact_path, historical = _write_artifact(tmp_path)
    renamed = tmp_path / "renamed.json"
    renamed.write_bytes(historical.read_bytes())

    verification = verify_forward_edge_artifact_source(artifact_path, renamed)

    assert verification.status is ForwardEdgeArtifactSourceStatus.SOURCE_CHANGED
    assert verification.historical_validation_name_matches is False
    assert verification.source_matches is True
    assert verification.reasons == ("historical_validation_name_mismatch",)


def test_verify_cli_emits_json_and_exit_codes(tmp_path: Path) -> None:
    artifact_path, historical = _write_artifact(tmp_path)

    verified = runner.invoke(
        _app(),
        [
            "forward-edge-seal-verify",
            "--artifact",
            str(artifact_path),
            "--historical-validation",
            str(historical),
            "--output",
            "json",
        ],
    )

    assert verified.exit_code == 0, verified.output
    assert json.loads(verified.output)["status"] == "verified"

    _write_historical(historical, suffix="changed")
    changed = runner.invoke(
        _app(),
        [
            "forward-edge-seal-verify",
            "--artifact",
            str(artifact_path),
            "--historical-validation",
            str(historical),
        ],
    )

    assert changed.exit_code == 2
    assert "status=source_changed" in changed.output
    assert "source_matches=false" in changed.output


def test_verify_cli_rejects_invalid_output_before_verification(tmp_path: Path) -> None:
    artifact_path, historical = _write_artifact(tmp_path)

    result = runner.invoke(
        _app(),
        [
            "forward-edge-seal-verify",
            "--artifact",
            str(artifact_path),
            "--historical-validation",
            str(historical),
            "--output",
            "invalid",
        ],
    )

    assert result.exit_code != 0
    assert "output must be text or json" in result.output
