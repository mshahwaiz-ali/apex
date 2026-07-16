from __future__ import annotations

import hashlib
import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.p1_review_artifact import register_p1_review_artifact_commands
from apex.cli_commands.p1_review_artifact_verify import (
    register_p1_review_artifact_verify_commands,
)
from apex.paper_trading.p1_review_artifact import (
    build_p1_review_artifact,
    write_p1_review_artifact,
)
from apex.paper_trading.p1_review_artifact_verification import (
    P1ReviewArtifactSourceStatus,
    verify_p1_review_artifact_sources,
)

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_p1_review_artifact_commands(app)
    register_p1_review_artifact_verify_commands(app)
    return app


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
    payload["report_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _sources(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "review_report_path": tmp_path / "review.json",
        "historical_profile_path": tmp_path / "historical.json",
        "forward_profile_path": tmp_path / "forward.json",
        "daily_report_path": tmp_path / "daily.json",
        "paper_store_path": tmp_path / "trades.json",
    }
    _write_review(paths["review_report_path"])
    for label, path in paths.items():
        if label != "review_report_path":
            path.write_text("{}\n", encoding="utf-8")
    return paths


def _verify_args(artifact: Path, sources: dict[str, Path]) -> list[str]:
    return [
        "p1-review-seal-verify",
        "--artifact",
        str(artifact),
        "--review-report",
        str(sources["review_report_path"]),
        "--historical-profile",
        str(sources["historical_profile_path"]),
        "--forward-profile",
        str(sources["forward_profile_path"]),
        "--daily-report",
        str(sources["daily_report_path"]),
        "--paper-store",
        str(sources["paper_store_path"]),
    ]


def test_commands_are_registered() -> None:
    result = runner.invoke(_app(), ["--help"])

    assert result.exit_code == 0
    assert "p1-review-seal" in result.output
    assert "p1-review-seal-verify" in result.output


def test_source_verification_accepts_exact_evidence_and_rejects_change(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    artifact_path = tmp_path / "sealed.json"
    artifact = build_p1_review_artifact(**sources)
    write_p1_review_artifact(artifact_path, artifact)

    verified = verify_p1_review_artifact_sources(artifact_path, **sources)
    assert verified.status is P1ReviewArtifactSourceStatus.VERIFIED
    assert all(verified.source_matches.values())
    assert all(verified.source_name_matches.values())
    assert verified.reasons == ()

    sources["paper_store_path"].write_text('{"changed": true}\n', encoding="utf-8")
    changed = verify_p1_review_artifact_sources(artifact_path, **sources)
    assert changed.status is P1ReviewArtifactSourceStatus.SOURCE_CHANGED
    assert changed.source_matches["paper_store"] is False
    assert changed.reasons == ("paper_store_hash_mismatch",)


def test_source_verification_rejects_renamed_source(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    artifact_path = tmp_path / "sealed.json"
    write_p1_review_artifact(artifact_path, build_p1_review_artifact(**sources))
    renamed = tmp_path / "renamed.json"
    renamed.write_bytes(sources["daily_report_path"].read_bytes())
    sources["daily_report_path"] = renamed

    verification = verify_p1_review_artifact_sources(artifact_path, **sources)

    assert verification.status is P1ReviewArtifactSourceStatus.SOURCE_CHANGED
    assert verification.source_matches["daily_report"] is True
    assert verification.source_name_matches["daily_report"] is False
    assert verification.reasons == ("daily_report_name_mismatch",)


def test_seal_and_verify_cli_json_and_exit_codes(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    artifact_path = tmp_path / "sealed.json"
    seal = runner.invoke(
        _app(),
        [
            "p1-review-seal",
            "--review-report",
            str(sources["review_report_path"]),
            "--historical-profile",
            str(sources["historical_profile_path"]),
            "--forward-profile",
            str(sources["forward_profile_path"]),
            "--daily-report",
            str(sources["daily_report_path"]),
            "--paper-store",
            str(sources["paper_store_path"]),
            "--output",
            str(artifact_path),
        ],
    )

    assert seal.exit_code == 0, seal.output
    assert "P1_REVIEW_ARTIFACT_SEALED" in seal.output

    verified = runner.invoke(_app(), [*_verify_args(artifact_path, sources), "--output", "json"])
    assert verified.exit_code == 0, verified.output
    assert json.loads(verified.output)["status"] == "verified"

    sources["forward_profile_path"].write_text('{"changed": true}\n', encoding="utf-8")
    changed = runner.invoke(_app(), _verify_args(artifact_path, sources))
    assert changed.exit_code == 2
    assert "status=source_changed" in changed.output
    assert "mismatched=forward_profile" in changed.output


def test_seal_requires_force_and_verify_rejects_invalid_output(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    artifact_path = tmp_path / "sealed.json"
    write_p1_review_artifact(artifact_path, build_p1_review_artifact(**sources))

    blocked = runner.invoke(
        _app(),
        [
            "p1-review-seal",
            "--review-report",
            str(sources["review_report_path"]),
            "--historical-profile",
            str(sources["historical_profile_path"]),
            "--forward-profile",
            str(sources["forward_profile_path"]),
            "--daily-report",
            str(sources["daily_report_path"]),
            "--paper-store",
            str(sources["paper_store_path"]),
            "--output",
            str(artifact_path),
        ],
    )
    assert blocked.exit_code != 0
    assert "refusing to overwrite P1 review artifact" in blocked.output

    invalid = runner.invoke(
        _app(),
        [*_verify_args(artifact_path, sources), "--output", "invalid"],
    )
    assert invalid.exit_code != 0
    assert "output must be text or json" in invalid.output
