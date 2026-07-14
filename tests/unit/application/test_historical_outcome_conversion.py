from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.application.historical_edge import DatasetPartition, DatasetSplit, MarketType
from apex.application.historical_outcome_conversion import (
    OutcomeRejectionReason,
    convert_backtest_trades,
)
from apex.backtesting import BacktestOutcome, BacktestSignal, SimulatedTrade
from apex.strategies import StrategyType, TradeDirection

_START = datetime(2026, 1, 1, tzinfo=UTC)
_PARTITIONS = (
    DatasetPartition(DatasetSplit.TRAIN, _START, _START + timedelta(days=10)),
    DatasetPartition(
        DatasetSplit.VALIDATION,
        _START + timedelta(days=10),
        _START + timedelta(days=15),
    ),
    DatasetPartition(
        DatasetSplit.TEST,
        _START + timedelta(days=15),
        _START + timedelta(days=20),
    ),
)


def _trade(
    *,
    outcome: BacktestOutcome = BacktestOutcome.TARGET,
    entry_time: datetime = _START + timedelta(days=1),
    exit_time: datetime | None = None,
    net_pnl: float = 39.0,
    fees: float = 1.0,
    metadata: dict[str, str | int | float | bool] | None = None,
) -> SimulatedTrade:
    signal = BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=entry_time - timedelta(minutes=5),
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=10.0,
        risk_amount=20.0,
        confidence_score=80.0,
    )
    evidence: dict[str, str | int | float | bool] = {
        "entry_time": entry_time.isoformat(),
        "executed_entry_price": 100.0,
        "regime": "TREND",
        "maximum_favorable_excursion_r": 2.0,
        "maximum_adverse_excursion_r": -0.25,
    }
    if metadata:
        evidence.update(metadata)
    return SimulatedTrade(
        signal=signal,
        outcome=outcome,
        exit_time=exit_time or entry_time + timedelta(minutes=30),
        exit_price=104.0,
        gross_pnl=net_pnl + fees,
        fees=fees,
        net_pnl=net_pnl,
        realized_r_multiple=net_pnl / signal.risk_amount,
        holding_candles=6,
        metadata=evidence,
    )


def _convert(*trades: SimulatedTrade):
    return convert_backtest_trades(
        trades,
        dataset_id="curated-futures-001",
        market_type=MarketType.FUTURES,
        partitions=_PARTITIONS,
        source_identity="campaign-001/run-baseline",
    )


def test_completed_trade_is_assigned_by_actual_entry_time() -> None:
    summary = _convert(_trade(entry_time=_START + timedelta(days=11)))

    assert summary.accepted_count == 1
    assert summary.outcomes[0].split is DatasetSplit.VALIDATION
    assert summary.outcomes[0].market_type is MarketType.FUTURES
    assert summary.outcomes[0].score_band == "75-84"


def test_net_return_preserves_fee_adjusted_net_pnl() -> None:
    summary = _convert(_trade(net_pnl=39.0, fees=1.0))

    assert summary.outcomes[0].net_return == pytest.approx(39.0 / 1000.0)
    assert summary.outcomes[0].r_multiple == pytest.approx(1.95)


def test_missed_entry_is_rejected() -> None:
    summary = _convert(_trade(outcome=BacktestOutcome.MISSED_ENTRY, net_pnl=0.0, fees=0.0))

    assert summary.accepted_count == 0
    assert summary.rejection_reasons == {OutcomeRejectionReason.MISSED_ENTRY.value: 1}


def test_trade_outside_all_partitions_is_rejected() -> None:
    summary = _convert(
        _trade(
            entry_time=_START - timedelta(days=1),
            exit_time=_START - timedelta(days=1, minutes=-30),
        )
    )

    assert summary.rejections[0].reason is OutcomeRejectionReason.OUTSIDE_PARTITIONS


def test_trade_spanning_partition_boundary_is_rejected() -> None:
    summary = _convert(
        _trade(
            entry_time=_START + timedelta(days=9, hours=23),
            exit_time=_START + timedelta(days=10, minutes=1),
        )
    )

    assert summary.rejections[0].reason is OutcomeRejectionReason.PARTITION_SPAN


def test_unavailable_excursion_metric_is_not_fabricated() -> None:
    trade = _trade()
    metadata = dict(trade.metadata)
    metadata.pop("maximum_favorable_excursion_r")
    incomplete = SimulatedTrade(
        signal=trade.signal,
        outcome=trade.outcome,
        exit_time=trade.exit_time,
        exit_price=trade.exit_price,
        gross_pnl=trade.gross_pnl,
        fees=trade.fees,
        net_pnl=trade.net_pnl,
        realized_r_multiple=trade.realized_r_multiple,
        holding_candles=trade.holding_candles,
        metadata=metadata,
    )

    summary = _convert(incomplete)

    assert summary.rejections[0].reason is OutcomeRejectionReason.MISSING_MFE_R


def test_duplicate_outcome_is_detected_deterministically() -> None:
    trade = _trade()
    first = _convert(trade, trade)
    second = _convert(trade, trade)

    assert first.accepted_count == 1
    assert first.duplicate_count == 1
    assert first.rejections[0].reason is OutcomeRejectionReason.DUPLICATE_OUTCOME
    assert first.result_hash == second.result_hash
    assert first.outcomes[0].setup_id == second.outcomes[0].setup_id


def test_market_type_is_explicit_and_not_inferred() -> None:
    spot = convert_backtest_trades(
        (_trade(),),
        dataset_id="curated-spot-001",
        market_type=MarketType.SPOT,
        partitions=_PARTITIONS,
        source_identity="spot-run",
    )

    assert spot.outcomes[0].market_type is MarketType.SPOT
