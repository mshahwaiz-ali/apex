"""Focused CLI coverage for integrated validation pipelines."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.validation_pipeline import register_validation_pipeline_commands

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_validation_pipeline_commands(app)
    return app


def test_pipeline_commands_are_registered() -> None:
    result = runner.invoke(_app(), ["--help"])

    assert result.exit_code == 0
    assert "paper-validation-run" in result.stdout
    assert "funded-readiness-from-report" in result.stdout


def test_funded_readiness_consumes_saved_p1_report(tmp_path: Path) -> None:
    p1_path = tmp_path / "p1.json"
    p1_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-07-14T11:00:00+00:00",
                "eligibility": "READY_FOR_FUNDED_REVIEW",
                "reasons": [],
                "closed_paper_trades": 40,
                "modeled_trades": 100,
                "win_rate_deviation": 0.02,
                "expectancy_deviation": 0.125,
                "drawdown_increase": 0.10,
            }
        ),
        encoding="utf-8",
    )
    checklist = {
        "analysis_reviewed": True,
        "risk_reviewed": True,
        "account_state_reviewed": True,
        "order_or_fill_verified": True,
        "lifecycle_recorded": True,
    }
    r1_path = tmp_path / "r1.json"
    r1_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-14T12:00:00+00:00",
                "provider_limits": {
                    "provider_name": "VERIFIED_PROVIDER",
                    "verified_on": "2026-07-14",
                    "external_daily_drawdown_limit_pct": 5.0,
                    "external_total_drawdown_limit_pct": 10.0,
                    "maximum_trades_per_day": 3,
                    "limits_verified": True,
                },
                "risk_mode": "STANDARD",
                "account_policy_type": "FUNDED",
                "account_policy_decision": {
                    "approved": True,
                    "lockout_reasons": [],
                    "daily_drawdown_pct": 0.0,
                    "total_drawdown_pct": 0.0,
                    "projected_total_open_risk_pct": 0.25,
                    "projected_directional_exposure_pct": 0.25,
                    "projected_correlated_exposure_pct": 0.25,
                },
                "daily_lockout_verified": True,
                "total_buffer_verified": True,
                "pre_trade_checklist": checklist,
                "post_trade_checklist": checklist,
                "kill_switch_state": "enabled",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        _app(),
        [
            "funded-readiness-from-report",
            str(r1_path),
            "--forward-validation-report",
            str(p1_path),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ready"] is True
    assert payload["reasons"] == []
