"""Tests for paper intake, evidence, and operational review presentation."""

from __future__ import annotations

import json

import pytest
import typer

from apex.cli_commands.paper_evidence_progress import (
    _resolve_presentation_mode as resolve_evidence_mode,
)
from apex.cli_commands.paper_intake import (
    _emit_summary,
    _resolve_presentation_mode as resolve_intake_mode,
)
from apex.paper_trading.intake import IntakeMarketType, IntakeSummary
from apex.presentation import OutputMode
from apex.presentation.paper_progress import (
    render_evidence_progress,
    render_operational_review,
    render_paper_intake,
)


def test_intake_text_is_operator_facing() -> None:
    rendered = render_paper_intake(
        {
            "market_type": "futures",
            "candidates_observed": 5,
            "accepted": 2,
            "rejected": 2,
            "duplicates_skipped": 1,
            "persistence_failures": 0,
            "reason_counts": {"candidate_rejected": 2},
            "created_trade_ids": ["paper-1", "paper-2"],
        }
    )

    assert "Paper Opportunity Intake" in rendered
    assert "Trades accepted" in rendered
    assert "Run the paper lifecycle cycle" in rendered
    assert "PAPER_INTAKE" not in rendered


def test_intake_verbose_includes_created_identifiers() -> None:
    rendered = render_paper_intake(
        {
            "market_type": "spot",
            "candidates_observed": 1,
            "accepted": 1,
            "created_trade_ids": ["paper-spot-1"],
        },
        mode="verbose",
    )

    assert "Created paper trades" in rendered
    assert "paper-spot-1" in rendered


def test_intake_json_preserves_canonical_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    summary = IntakeSummary(
        market_type=IntakeMarketType.FUTURES,
        candidates_observed=3,
        accepted=1,
        rejected=1,
        duplicates_skipped=1,
        persistence_failures=0,
        reason_counts={"ACCEPTED": 1},
        created_trade_ids=("paper-1",),
        results=(),
    )

    _emit_summary(summary, output="text", format_="json")

    payload = json.loads(capsys.readouterr().out)
    assert payload["market_type"] == "futures"
    assert payload["candidates_observed"] == 3
    assert payload["accepted"] == 1
    assert payload["created_trade_ids"] == ["paper-1"]


def test_format_overrides_legacy_output() -> None:
    assert resolve_intake_mode(output="json", format_="verbose") is OutputMode.VERBOSE
    assert resolve_evidence_mode(output="json", format_="debug") is OutputMode.DEBUG


@pytest.mark.parametrize(
    ("resolver", "format_value"),
    (
        (resolve_intake_mode, "yaml"),
        (resolve_evidence_mode, "compact"),
    ),
)
def test_invalid_format_fails_cleanly(
    resolver: object,
    format_value: str,
) -> None:
    with pytest.raises(ValueError, match="output mode must be one of"):
        resolver(output="text", format_=format_value)  # type: ignore[operator]


def test_invalid_legacy_output_fails_without_format() -> None:
    with pytest.raises(ValueError, match="legacy output must be text or json"):
        resolve_intake_mode(output="yaml", format_=None)


def test_evidence_progress_reports_readiness_and_largest_gap() -> None:
    rendered = render_evidence_progress(
        {
            "total_closed_trades": 35,
            "minimum_closed_trades": 25,
            "all_segments_sufficient": False,
            "segments": [
                {
                    "dimensions": {
                        "market_type": "futures",
                        "strategy": "breakout_retest",
                    },
                    "closed_trade_count": 10,
                    "minimum_closed_trades": 25,
                    "remaining_closed_trades": 15,
                    "sample_sufficient": False,
                    "win_rate": 0.6,
                    "expectancy_r": 0.25,
                    "profit_factor": 1.4,
                    "maximum_drawdown_r": 2.0,
                },
                {
                    "dimensions": {
                        "market_type": "futures",
                        "strategy": "trend_pullback",
                    },
                    "closed_trade_count": 25,
                    "minimum_closed_trades": 25,
                    "remaining_closed_trades": 0,
                    "sample_sufficient": True,
                    "win_rate": 0.52,
                    "expectancy_r": 0.12,
                    "profit_factor": 1.2,
                    "maximum_drawdown_r": 3.0,
                },
            ],
        }
    )

    assert "Overall readiness" in rendered
    assert "Not ready" in rendered
    assert "15 additional closed trades required" in rendered
    assert "Prioritize" in rendered
    assert "PAPER_EVIDENCE_PROGRESS" not in rendered


def test_empty_evidence_is_not_ready() -> None:
    rendered = render_evidence_progress(
        {
            "total_closed_trades": 0,
            "minimum_closed_trades": 100,
            "all_segments_sufficient": False,
            "segments": [],
        }
    )

    assert "No completed-trade segments are available yet." in rendered
    assert "Continue paper trading" in rendered


def test_review_hides_internal_milestone_labels() -> None:
    rendered = render_operational_review(
        {
            "review_state": "insufficient_sample",
            "production_eligible": False,
            "sample_sufficient": False,
            "manual_execution_usable": False,
        },
        output_path="data/review.json",
        anomaly_count=2,
    )

    assert "Paper Trading Operational Review" in rendered
    assert "Operationally ready" in rendered
    assert "Keep execution disabled" in rendered
    assert "P1" not in rendered
    assert "phase" not in rendered.lower()


def test_review_debug_adds_diagnostics() -> None:
    rendered = render_operational_review(
        {
            "review_state": "approved",
            "production_eligible": True,
            "sample_sufficient": True,
            "manual_execution_usable": True,
        },
        output_path="data/review.json",
        anomaly_count=0,
        mode="debug",
    )

    assert "Evidence quality" in rendered
    assert "Diagnostics" in rendered


def test_typer_bad_parameter_remains_available() -> None:
    assert issubclass(typer.BadParameter, Exception)
