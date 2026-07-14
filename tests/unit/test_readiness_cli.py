"""Focused CLI coverage for P1 and R1 review commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.readiness import register_readiness_commands

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_readiness_commands(app)
    return app


def test_readiness_commands_are_registered() -> None:
    result = runner.invoke(_app(), ["--help"])

    assert result.exit_code == 0
    assert "paper-validation-review" in result.stdout
    assert "funded-readiness-review" in result.stdout


def test_paper_validation_json_output_and_export(tmp_path: Path) -> None:
    input_path = tmp_path / "p1-input.json"
    report_path = tmp_path / "reports" / "p1.json"
    input_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-14T12:00:00+00:00",
                "backtest": {
                    "total_trades": 100,
                    "win_rate": 0.60,
                    "expectancy": 0.40,
                    "maximum_drawdown": 10.0,
                },
                "paper": {"closed_trades": 40, "win_rate": 0.58},
                "evidence": {
                    "paper_expectancy": 0.35,
                    "paper_maximum_drawdown": 11.0,
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        _app(),
        [
            "paper-validation-review",
            str(input_path),
            "--output",
            "json",
            "--report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    assert payload["eligibility"] == "READY_FOR_FUNDED_REVIEW"
    assert json.loads(report_path.read_text(encoding="utf-8")) == payload
    assert report_path.read_text(encoding="utf-8").endswith("\n")


def test_funded_readiness_blocks_unverified_provider(tmp_path: Path) -> None:
    input_path = tmp_path / "r1-input.json"
    input_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-14T12:00:00+00:00",
                "provider_limits": {
                    "provider_name": "UNVERIFIED_PROVIDER",
                    "verified_on": "2026-07-14",
                    "external_daily_drawdown_limit_pct": 5.0,
                    "external_total_drawdown_limit_pct": 10.0,
                    "maximum_trades_per_day": 3,
                    "limits_verified": False,
                },
                "forward_validation": {
                    "schema_version": 1,
                    "generated_at": "2026-07-14T11:00:00+00:00",
                    "eligibility": "READY_FOR_FUNDED_REVIEW",
                    "reasons": [],
                    "closed_paper_trades": 40,
                    "modeled_trades": 100,
                    "win_rate_deviation": 0.02,
                    "expectancy_deviation": 0.125,
                    "drawdown_increase": 0.10,
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
                "pre_trade_checklist": {
                    "analysis_reviewed": True,
                    "risk_reviewed": True,
                    "account_state_reviewed": True,
                    "order_or_fill_verified": True,
                    "lifecycle_recorded": True,
                },
                "post_trade_checklist": {
                    "analysis_reviewed": True,
                    "risk_reviewed": True,
                    "account_state_reviewed": True,
                    "order_or_fill_verified": True,
                    "lifecycle_recorded": True,
                },
                "kill_switch_state": "enabled",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        _app(),
        ["funded-readiness-review", str(input_path), "--output", "json"],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ready"] is False
    assert payload["reasons"] == ["PROVIDER_LIMITS_UNVERIFIED"]
