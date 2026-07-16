"""Tests for paper-trading operations presentation."""

from __future__ import annotations

from apex.presentation.paper import (
    render_paper_cycle,
    render_paper_pipeline,
    render_paper_report,
    render_paper_status,
    render_paper_trade,
)


def test_opened_trade_presentation_is_actionable() -> None:
    rendered = render_paper_trade(
        {
            "result": "opened",
            "current_action": "monitor",
            "instruction": "Monitor stop and targets.",
            "trade": {
                "trade_id": "paper-1",
                "state": "entered",
                "signal": {"symbol": "BTCUSDT", "direction": "long"},
                "futures_plan": {
                    "ideal_entry": 100.0,
                    "stop_loss": 98.0,
                    "selected_leverage": 10,
                    "quantity": 2.0,
                    "required_margin": 20.0,
                    "wallet_exposure_pct": 20.0,
                    "maximum_modeled_loss": 4.0,
                },
            },
        }
    )

    assert "Paper Trade — BTCUSDT" in rendered
    assert "Lifecycle state" in rendered
    assert "Entered" in rendered
    assert "10x" in rendered
    assert "Wallet exposure" in rendered
    assert "Maximum modeled loss" in rendered
    assert "Monitor stop and targets." in rendered


def test_rejected_plan_presentation_explains_block() -> None:
    rendered = render_paper_trade(
        {
            "symbol": "ETHUSDT",
            "status": "rejected",
            "reasons": ["Liquidation buffer is insufficient."],
        }
    )

    assert "Blocked or rejected" in rendered
    assert "Liquidation buffer is insufficient." in rendered
    assert "Do not open the trade" in rendered


def test_partial_exit_and_completed_trade_actions() -> None:
    partial = render_paper_trade(
        {
            "trade": {
                "state": "partially_closed",
                "signal": {"symbol": "SOLUSDT", "direction": "long"},
            }
        }
    )
    completed = render_paper_trade(
        {
            "trade": {
                "state": "target_hit",
                "signal": {"symbol": "SOLUSDT", "direction": "long"},
            }
        }
    )

    assert "Protect the remaining position" in partial
    assert "No further execution action is required" in completed


def test_verbose_trade_adds_lifecycle_and_fill_details() -> None:
    rendered = render_paper_trade(
        {
            "trade": {
                "state": "partially_closed",
                "signal": {"symbol": "XRPUSDT", "direction": "short"},
                "events": [{"event_type": "entry_filled", "price": 1.0}],
                "fills": [{"type": "partial_target", "price": 0.9}],
            }
        },
        mode="verbose",
    )

    assert "Lifecycle events" in rendered
    assert "Entry filled" in rendered
    assert "Fills and exits" in rendered
    assert "Partial target" in rendered


def test_cycle_presentation_reports_advancement_and_failures() -> None:
    rendered = render_paper_cycle(
        {
            "cycle": {
                "market_type": "futures",
                "eligible_trade_count": 3,
                "advanced_trade_count": 1,
                "unchanged_trade_count": 2,
            },
            "provider_failures": [{"symbol": "DOGEUSDT", "reason": "timeout"}],
            "fully_collected": False,
        }
    )

    assert "Paper Trading Cycle" in rendered
    assert "Advanced trades" in rendered
    assert "DOGEUSDT: timeout" in rendered
    assert "Review provider failures" in rendered


def test_pipeline_presentation_summarizes_evidence() -> None:
    rendered = render_paper_pipeline(
        {
            "market_type": "futures",
            "intake": {
                "candidates_observed": 6,
                "accepted": 2,
                "rejected": 3,
                "duplicates_skipped": 1,
            },
            "cycle": {
                "runtime": {
                    "cycle": {"advanced_trade_count": 1, "unchanged_trade_count": 1},
                    "provider_failures": [],
                }
            },
            "lifecycle_analytics": {
                "waiting_for_entry": 1,
                "entered_trades": 1,
                "partial_target_fills": 1,
                "full_target_completions": 0,
                "stop_loss_exits": 0,
                "invalidations": 0,
                "realized_net_pnl": 3.5,
                "average_realized_r_multiple": 0.75,
            },
        }
    )

    assert "Paper Trading Pipeline" in rendered
    assert "Lifecycle evidence" in rendered
    assert "Partial exits" in rendered
    assert "3.50" in rendered
    assert "0.75R" in rendered


def test_status_presentation_reports_scheduler_health() -> None:
    rendered = render_paper_status(
        {
            "operations_ready": False,
            "scheduler_ready": False,
            "total_trade_count": 12,
            "daily_report_count": 4,
            "review_report_count": 2,
            "markets": [
                {
                    "market_type": "futures",
                    "operationally_ready": False,
                    "latest_pipeline_outcome": "failed",
                    "consecutive_pipeline_failures": 2,
                    "open_trade_count": 1,
                    "closed_trade_count": 11,
                }
            ],
        }
    )

    assert "Paper Trading Operations Status" in rendered
    assert "Scheduler ready" in rendered
    assert "Investigate the latest pipeline failure" in rendered


def test_report_presentation_covers_guidance_and_debug() -> None:
    payload = {
        "performance": {
            "total_trades": 2,
            "open_trades": 1,
            "closed_trades": 1,
            "net_pnl": 5.0,
            "win_rate": 0.5,
        },
        "guidance": {
            "trades": [
                {
                    "trade_id": "paper-2",
                    "symbol": "BTCUSDT",
                    "paper_state": "entered",
                    "current_action": "monitor",
                    "instruction": "Monitor active risk.",
                }
            ]
        },
    }

    text = render_paper_report(payload)
    debug = render_paper_report(payload, mode="debug")

    assert "Paper Trading Report" in text
    assert "Monitor active risk." in text
    assert "50.0%" in text
    assert "Trade details" in debug
    assert "Deterministic payload summary" in debug
