"""Tests for professional research workflow presentation."""

from __future__ import annotations

import inspect
import json

import typer
from typer.testing import CliRunner

from apex.cli_commands.research_overlay import install_research_output_overlay
from apex.presentation.research import (
    render_backtest,
    render_campaign,
    render_dataset_export,
    render_edge_report,
    render_edge_validation,
)


def test_backtest_renders_core_performance_and_verbose_diagnostics() -> None:
    payload = {
        "symbol": "BTCUSDT",
        "dataset_source": "fixture.json",
        "risk_mode": "AGGRESSIVE",
        "metadata": {"replay_timeframe": "5m"},
        "decision_count": 80,
        "approved_count": 12,
        "skipped_count": 68,
        "failure_count": 0,
        "failures": {},
        "metrics": {
            "trade_count": 12,
            "win_rate": 58.3,
            "profit_factor": 1.42,
            "expectancy_r": 0.18,
            "max_drawdown_percentage": 7.4,
        },
        "diagnostics": {"rejection_code_counts": {"low_score": 14}},
    }

    text = render_backtest(payload)
    verbose = render_backtest(payload, mode="verbose")

    assert "Historical Backtest — BTCUSDT" in text
    assert "Profit factor" in text
    assert "1.42" in text
    assert "Execution Diagnostics" not in text
    assert "Execution Diagnostics" in verbose


def test_campaign_renders_variant_results() -> None:
    payload = {
        "campaign_id": "campaign-1",
        "risk_mode": "STANDARD",
        "dataset_source": "fixture.json",
        "variants": [
            {
                "variant_id": "baseline",
                "metrics": {"trade_count": 20, "profit_factor": 1.25, "expectancy_r": 0.12},
            }
        ],
    }

    rendered = render_campaign(payload)

    assert "Historical Backtest Campaign" in rendered
    assert "baseline" in rendered
    assert "profit factor 1.25" in rendered


def test_edge_and_validation_render_completion_fields() -> None:
    edge = render_edge_report(
        {
            "campaign_id": "campaign-1",
            "trade_count": 120,
            "profile_count": 8,
            "report_id": "edge-1",
        },
        output_path="edge.json",
    )
    validation = render_edge_validation(
        {
            "campaign_id": "campaign-1",
            "segment_count": 8,
            "validated_out_of_sample_count": 5,
            "report_id": "validation-1",
        },
        output_path="validation.json",
    )

    assert "Trades   : 120" in edge
    assert "Profiles : 8" in edge
    assert "Validated out-of-sample: 5" in validation


def test_dataset_export_renders_candle_count() -> None:
    payload = {
        "symbol": "BTCUSDT",
        "source": "Binance",
        "candles": [
            {"timeframe": "1m"},
            {"timeframe": "5m"},
        ],
    }

    rendered = render_dataset_export(payload, output_path="dataset.json", mode="verbose")

    assert "Closed candles: 2" in rendered
    assert "1m, 5m" in rendered


def test_overlay_adds_format_and_preserves_json_mode() -> None:
    app = typer.Typer()

    @app.command("compare-backtests")
    def compare_backtests() -> None:
        typer.echo(json.dumps({"winner": "right", "delta": 0.25}))

    install_research_output_overlay(app)
    command = next(item for item in app.registered_commands if item.name == "compare-backtests")
    assert command.callback is not None
    assert "output_format" in inspect.signature(command.callback).parameters

    runner = CliRunner()
    json_result = runner.invoke(app, ["compare-backtests", "--format", "json"])
    text_result = runner.invoke(app, ["compare-backtests"])

    assert json_result.exit_code == 0
    assert json.loads(json_result.stdout) == {"winner": "right", "delta": 0.25}
    assert text_result.exit_code == 0
    assert "Backtest Comparison" in text_result.stdout
