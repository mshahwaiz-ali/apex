from __future__ import annotations

from datetime import UTC, datetime

from apex.application.paper_lifecycle_analytics import (
    build_paper_lifecycle_analytics,
    paper_lifecycle_analytics_payload,
)
from apex.backtesting import BacktestSignal
from apex.paper_trading.contracts import PaperTrade, PaperTradeState
from apex.paper_trading.intake import IntakeMarketType, IntakeSummary
from apex.paper_trading.operations import PaperOperationCycleResult
from apex.paper_trading.runtime import PaperRuntimeResult
from apex.strategies import StrategyType, TradeDirection


def _signal() -> BacktestSignal:
    timestamp = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    return BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=TradeDirection.LONG,
        generated_at=timestamp,
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=2.0,
        risk_amount=4.0,
        confidence_score=80.0,
        target_prices=(102.0, 104.0),
        partial_close_percentages=(50.0, 50.0),
    )


def _intake() -> IntakeSummary:
    return IntakeSummary(
        market_type=IntakeMarketType.FUTURES,
        candidates_observed=3,
        accepted=2,
        rejected=0,
        duplicates_skipped=1,
        persistence_failures=0,
        reason_counts={"ACCEPTED": 2, "DUPLICATE_SKIPPED": 1},
        created_trade_ids=("trade-entered", "trade-invalidated"),
        results=(),
    )


def _runtime() -> PaperRuntimeResult:
    timestamp = datetime(2026, 7, 16, 12, 5, tzinfo=UTC)
    cycle = PaperOperationCycleResult(
        market_type="futures",
        started_at=timestamp,
        completed_at=timestamp,
        loaded_trade_count=2,
        eligible_trade_count=2,
        advanced_trade_count=1,
        unchanged_trade_count=1,
        missing_candle_trade_ids=("trade-invalidated",),
        trade_ids=("trade-entered", "trade-invalidated"),
    )
    return PaperRuntimeResult(
        cycle=cycle,
        requested_symbols=("BTCUSDT", "ETHUSDT"),
        successful_symbols=("BTCUSDT",),
        provider_failures=(("ETHUSDT", "provider unavailable"),),
    )


def test_builds_complete_intake_runtime_and_trade_analytics() -> None:
    timestamp = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    entered = PaperTrade(
        trade_id="trade-entered",
        signal=_signal(),
        state=PaperTradeState.TARGET_HIT,
        created_at=timestamp,
        updated_at=timestamp,
        analysis_payload={
            "market_type": "futures",
            "strategy": "breakout_continuation",
            "direction": "long",
            "setup_segment": {
                "scanner_type": "legacy-category",
                "gainer_state": "legacy-state",
            },
        },
        futures_plan={
            "entry": {"state": "ready_now"},
            "required_leverage": 12.0,
            "required_margin": 20.0,
            "wallet_exposure_pct": 20.0,
            "estimated_liquidation_price": 92.0,
            "fee_allowance": 0.4,
            "slippage_allowance": 0.2,
        },
        lifecycle_events=(
            {"event_type": "setup_generated", "occurred_at": timestamp.isoformat()},
            {"event_type": "entry_filled", "occurred_at": timestamp.isoformat()},
            {
                "event_type": "partial_target_hit",
                "occurred_at": timestamp.isoformat(),
                "reason": "target 1 hit",
            },
            {
                "event_type": "full_target_hit",
                "occurred_at": timestamp.isoformat(),
                "reason": "target 2 hit",
            },
        ),
        entry_time=timestamp,
        entry_price=100.1,
        exit_time=timestamp,
        exit_price=103.9,
        net_pnl=7.0,
        realized_r_multiple=1.75,
        partial_target_count=2,
        closed_percentage=100.0,
        candles_waited=1,
        candles_held=8,
    )
    invalidated = PaperTrade(
        trade_id="trade-invalidated",
        signal=_signal(),
        state=PaperTradeState.INVALIDATED,
        created_at=timestamp,
        updated_at=timestamp,
        analysis_payload={"market_type": "futures"},
        lifecycle_events=(
            {"event_type": "setup_generated", "occurred_at": timestamp.isoformat()},
            {
                "event_type": "invalidated",
                "occurred_at": timestamp.isoformat(),
                "reason": "stop violated before entry",
            },
        ),
        exit_time=timestamp,
        exit_price=98.0,
        candles_waited=2,
    )

    analytics = build_paper_lifecycle_analytics(
        intake=_intake(),
        runtime=_runtime(),
        trades=(invalidated, entered),
    )
    payload = paper_lifecycle_analytics_payload(analytics)

    assert payload["intake_candidates_observed"] == 3
    assert payload["duplicates_skipped"] == 1
    assert payload["provider_failure_count"] == 1
    assert payload["provider_failures_by_symbol"] == {"ETHUSDT": 1}
    assert payload["entered_trades"] == 1
    assert payload["unfilled_terminal_trades"] == 1
    assert payload["partial_target_fills"] == 2
    assert payload["full_target_completions"] == 1
    assert payload["invalidations"] == 1
    assert payload["realized_net_pnl"] == 7.0
    assert payload["average_realized_r_multiple"] == 0.875
    assert payload["risk_multiple_distribution"] == {
        "0r_to_1r": 1,
        "1r_to_2r": 1,
    }
    assert payload["leverage_distribution"] == {"10_20x": 1}
    assert payload["holding_time_distribution"] == {
        "6_12_candles": 1,
        "not_entered": 1,
    }
    assert payload["transition_counts"]["entry_filled"] == 1
    assert payload["transition_reason_counts"]["stop violated before entry"] == 1
    assert [trade["trade_id"] for trade in payload["trades"]] == [
        "trade-entered",
        "trade-invalidated",
    ]
    assert "scanner_type" not in payload["trades"][0]
    assert "gainer_state" not in payload["trades"][0]


def test_partial_inputs_remain_empty_without_fabricated_financials() -> None:
    analytics = build_paper_lifecycle_analytics(intake=None, runtime=None)
    payload = paper_lifecycle_analytics_payload(analytics)

    assert payload["intake_candidates_observed"] == 0
    assert payload["provider_failure_count"] == 0
    assert payload["realized_net_pnl"] is None
    assert payload["average_realized_r_multiple"] is None
    assert payload["average_margin"] is None
    assert payload["total_fees"] is None
    assert payload["trades"] == ()
