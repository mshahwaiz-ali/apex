from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.funded_history_readiness_artifact import (
    register_funded_history_readiness_artifact_commands,
)
from apex.cli_commands.funded_history_readiness_artifact_verify import (
    register_funded_history_readiness_artifact_verify_commands,
)
from apex.funded.history_readiness_artifact import (
    build_funded_history_readiness_artifact,
    write_funded_history_readiness_artifact,
)
from apex.funded.history_readiness_artifact_verification import (
    FundedHistoryReadinessArtifactSourceStatus,
    verify_funded_history_readiness_artifact_sources,
)

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_funded_history_readiness_artifact_commands(app)
    register_funded_history_readiness_artifact_verify_commands(app)
    return app


def _write_input(path: Path) -> None:
    path.write_text(
        json.dumps({"provider_limits": {"provider_name": "Example Funded"}}, sort_keys=True)
        + "\n",
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


def _write_report(path: Path, *, ready: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-07-16T12:00:00+00:00",
                "ready": ready,
                "provider_name": "Example Funded",
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


def _verify_args(
    artifact: Path,
    input_path: Path,
    history_path: Path,
    report_path: Path,
) -> list[str]:
    return [
        "funded-history-readiness-seal-verify",
        "--artifact",
        str(artifact),
        "--input",
        str(input_path),
        "--history-review",
        str(history_path),
        "--report",
        str(report_path),
    ]


def test_commands_are_registered() -> None:
    result = runner.invoke(_app(), ["--help"])

    assert result.exit_code == 0
    assert "funded-history-readiness-seal" in result.output
    assert "funded-history-readiness-seal-verify" in result.output


def test_source_verification_accepts_exact_sources_and_rejects_change(tmp_path: Path) -> None:
    input_path, history_path, report_path = _sources(tmp_path)
    artifact_path = tmp_path / "sealed.json"
    write_funded_history_readiness_artifact(
        artifact_path,
        build_funded_history_readiness_artifact(
            input_path=input_path,
            history_review_path=history_path,
            report_path=report_path,
        ),
    )

    verified = verify_funded_history_readiness_artifact_sources(
        artifact_path,
        input_path=input_path,
        history_review_path=history_path,
        report_path=report_path,
    )
    assert verified.status is FundedHistoryReadinessArtifactSourceStatus.VERIFIED
    assert verified.reasons == ()

    _write_history(history_path, ready=False)
    changed = verify_funded_history_readiness_artifact_sources(
        artifact_path,
        input_path=input_path,
        history_review_path=history_path,
        report_path=report_path,
    )
    assert changed.status is FundedHistoryReadinessArtifactSourceStatus.SOURCE_CHANGED
    assert changed.source_matches["history_review"] is False
    assert changed.reasons == ("history_review_hash_mismatch",)


def test_source_verification_rejects_renamed_history_source(tmp_path: Path) -> None:
    input_path, history_path, report_path = _sources(tmp_path)
    artifact_path = tmp_path / "sealed.json"
    write_funded_history_readiness_artifact(
        artifact_path,
        build_funded_history_readiness_artifact(
            input_path=input_path,
            history_review_path=history_path,
            report_path=report_path,
        ),
    )
    renamed = tmp_path / "renamed-history.json"
    renamed.write_bytes(history_path.read_bytes())

    verification = verify_funded_history_readiness_artifact_sources(
        artifact_path,
        input_path=input_path,
        history_review_path=renamed,
        report_path=report_path,
    )

    assert verification.status is FundedHistoryReadinessArtifactSourceStatus.SOURCE_CHANGED
    assert verification.source_matches["history_review"] is True
    assert verification.source_name_matches["history_review"] is False
    assert verification.reasons == ("history_review_name_mismatch",)


def test_seal_and_verify_cli_json_and_exit_codes(tmp_path: Path) -> None:
    input_path, history_path, report_path = _sources(tmp_path)
    artifact_path = tmp_path / "sealed.json"
    sealed = runner.invoke(
        _app(),
        [
            "funded-history-readiness-seal",
            "--input",
            str(input_path),
            "--history-review",
            str(history_path),
            "--report",
            str(report_path),
            "--output",
            str(artifact_path),
        ],
    )

    assert sealed.exit_code == 0, sealed.output
    assert "FUNDED_HISTORY_READINESS_ARTIFACT_SEALED" in sealed.output

    verified = runner.invoke(
        _app(),
        [*_verify_args(artifact_path, input_path, history_path, report_path), "--output", "json"],
    )
    assert verified.exit_code == 0, verified.output
    assert json.loads(verified.output)["status"] == "verified"

    _write_history(history_path, ready=False)
    changed = runner.invoke(
        _app(),
        _verify_args(artifact_path, input_path, history_path, report_path),
    )
    assert changed.exit_code == 2
    assert "status=source_changed" in changed.output
    assert "mismatched=history_review" in changed.output


def test_seal_requires_force_and_verify_rejects_invalid_output(tmp_path: Path) -> None:
    input_path, history_path, report_path = _sources(tmp_path)
    artifact_path = tmp_path / "sealed.json"
    write_funded_history_readiness_artifact(
        artifact_path,
        build_funded_history_readiness_artifact(
            input_path=input_path,
            history_review_path=history_path,
            report_path=report_path,
        ),
    )

    blocked = runner.invoke(
        _app(),
        [
            "funded-history-readiness-seal",
            "--input",
            str(input_path),
            "--history-review",
            str(history_path),
            "--report",
            str(report_path),
            "--output",
            str(artifact_path),
        ],
    )
    assert blocked.exit_code != 0
    assert "refusing to overwrite funded history-readiness artifact" in blocked.output

    invalid = runner.invoke(
        _app(),
        [*_verify_args(artifact_path, input_path, history_path, report_path), "--output", "invalid"],
    )
    assert invalid.exit_code != 0
    assert "output must be text or json" in invalid.output
