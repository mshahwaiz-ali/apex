"""Tests for validation and readiness presentation."""

from __future__ import annotations

import inspect
import json

import typer
from typer.testing import CliRunner

from apex.cli_commands.validation_overlay import install_validation_output_overlay
from apex.presentation.validation import render_evidence_bundle, render_validation


def test_validation_renders_status_reasons_and_metrics() -> None:
    payload = {
        "eligibility": "PAPER_ONLY",
        "closed_paper_trades": 24,
        "modeled_trades": 120,
        "win_rate_deviation": 0.08,
        "expectancy_deviation": 0.15,
        "drawdown_increase": 0.12,
        "reasons": ["INSUFFICIENT_CLOSED_TRADES", "EXPECTANCY_DEVIATION"],
    }

    rendered = render_validation(payload, title="Paper Validation Review")

    assert "Paper Validation Review" in rendered
    assert "Closed paper trades" in rendered
    assert "24" in rendered
    assert "Win-rate deviation" in rendered
    assert "8.0%" in rendered
    assert "Blocking Reasons" in rendered
    assert "Insufficient closed trades" in rendered


def test_daily_validation_renders_history_and_strategy_shortfalls() -> None:
    payload = {
        "record": {
            "trading_date": "2026-07-16",
            "report": {
                "eligibility": "PAPER_ONLY",
                "closed_paper_trades": 18,
                "modeled_trades": 90,
                "reasons": ["INSUFFICIENT_CLOSED_TRADES"],
            },
            "closed_trades_by_strategy": {"breakout": 6, "reclaim": 12},
        },
        "history_count": 4,
        "minimum_per_strategy": 10,
        "strategy_sample_shortfalls": {"breakout": 4},
    }

    rendered = render_validation(payload, title="Daily Paper Validation", mode="verbose")

    assert "History" in rendered
    assert "Observed strategies" in rendered
    assert "Strategy Sample Shortfalls" in rendered
    assert "Breakout: 4" in rendered
    assert "Validation Details" in rendered


def test_evidence_bundle_renders_dimensions_and_availability() -> None:
    payload = {
        "status": "READY",
        "profile_id": "breakout-long",
        "dimensions": {"strategy": "breakout", "direction": "LONG"},
        "historical_validation": {"validated": True},
        "forward_validation": None,
        "gaps": ["FORWARD_EVIDENCE_MISSING"],
    }

    rendered = render_evidence_bundle(payload)

    assert "Evidence Bundle" in rendered
    assert "breakout-long" in rendered
    assert "Historical evidence: Available" in rendered
    assert "Forward evidence   : Unavailable" in rendered
    assert "Forward evidence missing" in rendered


def test_overlay_adds_format_and_preserves_json_mode() -> None:
    app = typer.Typer()

    @app.command("paper-validation-review")
    def paper_validation_review(output: str = "text") -> None:
        assert output == "json"
        typer.echo(json.dumps({"eligibility": "PAPER_ONLY", "reasons": []}))

    install_validation_output_overlay(app)
    command = next(item for item in app.registered_commands if item.name == "paper-validation-review")
    assert command.callback is not None
    assert "output_format" in inspect.signature(command.callback).parameters

    runner = CliRunner()
    json_result = runner.invoke(app, ["--format", "json"])
    text_result = runner.invoke(app, [])

    assert json_result.exit_code == 0
    assert json.loads(json_result.stdout) == {"eligibility": "PAPER_ONLY", "reasons": []}
    assert text_result.exit_code == 0
    assert "Paper Validation Review" in text_result.stdout
