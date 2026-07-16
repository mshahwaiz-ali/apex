from __future__ import annotations

import json
from datetime import UTC, datetime

from apex.application.paper_pipeline import PaperPipelineResult
from apex.backtesting import BacktestSignal
from apex.cli_commands.paper_pipeline import _emit_pipeline, _market_trades
from apex.paper_trading import (
    IntakeMarketType,
    IntakeSummary,
    PaperOperationCycleResult,
    PaperRuntimeResult,
    PaperTrade,
    PaperTradeState,
    ScheduledPaperCycleResult,
)
from apex.strategies import StrategyType, TradeDirection


def _signal(symbol: str) -> BacktestSignal:
    timestamp = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    return BacktestSignal(
        symbol=symbol,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=TradeDirection.LONG,
        generated_at=timestamp,
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=1.0,
        risk_amount=2.0,
        confidence_score=80.0,
    )


def _trade(trade_id: str, market_type: str) -> PaperTrade:
    timestamp = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    return PaperTrade(
        trade_id=trade_id,
        signal=_signal(f"{trade_id.upper()}USDT"),
        state=PaperTradeState.WAITING_FOR_ENTRY,
        created_at=timestamp,
        updated_at=timestamp,
        analysis_payload={"market_type": market_type},
    )


def _pipeline_result() -> PaperPipelineResult:
    timestamp = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    intake = IntakeSummary(
        market_type=IntakeMarketType.FUTURES,
        candidates_observed=2,
        accepted=1,
        rejected=1,
        duplicates_skipped=0,
        persistence_failures=0,
        reason_counts={"ACCEPTED": 1, "NO_APPROVED_SETUP": 1},
        created_trade_ids=("futures",),
        results=(),
    )
    cycle = PaperOperationCycleResult(
        market_type="futures",
        started_at=timestamp,
        completed_at=timestamp,
        loaded_trade_count=2,
        eligible_trade_count=1,
        advanced_trade_count=1,
        unchanged_trade_count=0,
        missing_candle_trade_ids=(),
        trade_ids=("futures",),
    )
    runtime = PaperRuntimeResult(
        cycle=cycle,
        requested_symbols=("BTCUSDT",),
        successful_symbols=("BTCUSDT",),
        provider_failures=(),
    )
    scheduled = ScheduledPaperCycleResult(
        market_type="futures",
        started_at=timestamp,
        completed_at=timestamp,
        runtime=runtime,
        lock_path="cycle.lock",
        log_path="cycle.jsonl",
    )
    return PaperPipelineResult(
        run_id="run-analytics",
        market_type=IntakeMarketType.FUTURES,
        started_at=timestamp,
        completed_at=timestamp,
        intake=intake,
        cycle=scheduled,
        lock_path="pipeline.lock",
        log_path="pipeline.jsonl",
        lifecycle_analytics={
            "waiting_for_entry": 1,
            "entered_trades": 1,
            "partial_target_fills": 2,
            "full_target_completions": 1,
            "stop_loss_exits": 0,
            "invalidations": 1,
            "realized_net_pnl": 3.25,
            "average_realized_r_multiple": 1.625,
        },
    )


def test_market_trades_isolates_spot_and_futures_histories() -> None:
    futures = _trade("futures", "futures")
    spot = _trade("spot", "spot")
    legacy = _trade("legacy", "")
    legacy.analysis_payload.pop("market_type")

    assert _market_trades((spot, futures, legacy), IntakeMarketType.SPOT) == (spot,)
    assert _market_trades((spot, futures, legacy), IntakeMarketType.FUTURES) == (
        futures,
        legacy,
    )


def test_text_output_includes_operator_facing_lifecycle_metrics(capsys) -> None:
    _emit_pipeline(_pipeline_result(), "text")

    output = capsys.readouterr().out
    assert "Paper Trading Pipeline" in output
    assert "Lifecycle evidence" in output
    assert "Waiting for entry" in output
    assert "Entered trades" in output
    assert "Partial exits" in output
    assert "Completed targets" in output
    assert "Invalidated" in output
    assert "Realized net PnL" in output
    assert "3.25" in output
    assert "Average realized R" in output
    assert "1.62R" in output


def test_json_output_preserves_lifecycle_analytics(capsys) -> None:
    _emit_pipeline(_pipeline_result(), "json")

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 3
    assert payload["lifecycle_analytics"]["entered_trades"] == 1
    assert payload["lifecycle_analytics"]["realized_net_pnl"] == 3.25
