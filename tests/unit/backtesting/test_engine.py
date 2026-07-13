from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting import (
    BacktestConfig,
    BacktestOutcome,
    BacktestRequest,
    BacktestSignal,
    HistoricalBacktestRunner,
    simulate_trade,
    summarize_trades,
)
from apex.domain import Candle
from apex.strategies import StrategyType, TradeDirection

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _signal(
    *,
    direction: TradeDirection = TradeDirection.LONG,
    target_prices: tuple[float, ...] = (),
    partial_close_percentages: tuple[float, ...] = (),
) -> BacktestSignal:
    return BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=direction,
        generated_at=NOW,
        entry_price=100.0,
        stop_price=98.0 if direction is TradeDirection.LONG else 102.0,
        target_price=(
            target_prices[0]
            if target_prices
            else (104.0 if direction is TradeDirection.LONG else 96.0)
        ),
        quantity=10.0,
        risk_amount=20.0,
        confidence_score=80.0,
        target_prices=target_prices,
        partial_close_percentages=partial_close_percentages,
    )


def _candle(
    *,
    high: float,
    low: float,
    close: float = 100.0,
    open_price: float = 100.0,
    index: int = 0,
) -> Candle:
    return Candle(
        symbol="BTC/USDT",
        timeframe="5m",
        open_time=NOW + timedelta(minutes=5 * index),
        close_time=NOW + timedelta(minutes=5 * (index + 1)),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        is_closed=True,
        source="fixture",
    )


def test_conservative_intrabar_ambiguity_uses_stop_first() -> None:
    trade = simulate_trade(
        _signal(),
        (_candle(high=105.0, low=97.0),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert trade.outcome is BacktestOutcome.STOP
    assert trade.net_pnl == pytest.approx(-20.0)
    assert trade.realized_r_multiple == pytest.approx(-1.0)


def test_non_conservative_intrabar_can_use_target_first() -> None:
    trade = simulate_trade(
        _signal(),
        (_candle(high=105.0, low=97.0),),
        config=BacktestConfig(
            fee_pct=0.0,
            slippage_pct=0.0,
            conservative_intrabar=False,
        ),
    )

    assert trade.outcome is BacktestOutcome.TARGET
    assert trade.net_pnl == pytest.approx(40.0)


def test_short_trade_target_and_summary_metrics() -> None:
    trade = simulate_trade(
        _signal(direction=TradeDirection.SHORT),
        (_candle(high=101.0, low=95.0),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    report = summarize_trades((trade,))

    assert trade.outcome is BacktestOutcome.TARGET
    assert trade.net_pnl == pytest.approx(40.0)
    assert report.total_trades == 1
    assert report.win_rate == pytest.approx(1.0)
    assert report.by_symbol == {"BTC/USDT": 1}
    assert report.by_strategy == {"trend_pullback": 1}
    assert report.metadata["total_targets"] == 1


def test_simulated_trade_realizes_partial_target_before_stop() -> None:
    trade = simulate_trade(
        _signal(target_prices=(102.0, 104.0), partial_close_percentages=(50.0, 50.0)),
        (
            _candle(high=102.5, low=99.0, close=101.0, index=0),
            _candle(high=101.0, low=97.5, close=98.0, index=1),
        ),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert trade.outcome is BacktestOutcome.STOP
    assert trade.gross_pnl == pytest.approx(0.0)
    assert trade.metadata["partial_target_count"] == 1
    assert trade.metadata["closed_percentage"] == pytest.approx(50.0)


def test_simulated_trade_can_complete_target_ladder() -> None:
    trade = simulate_trade(
        _signal(target_prices=(102.0, 104.0), partial_close_percentages=(50.0, 50.0)),
        (_candle(high=104.5, low=99.0, close=104.0),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert trade.outcome is BacktestOutcome.TARGET
    assert trade.gross_pnl == pytest.approx(30.0)
    assert trade.metadata["partial_target_count"] == 2
    assert trade.metadata["closed_percentage"] == pytest.approx(100.0)


def test_backtest_signal_rejects_invalid_partial_percentages() -> None:
    with pytest.raises(ValueError, match="sum to 100"):
        _signal(target_prices=(102.0, 104.0), partial_close_percentages=(40.0, 40.0))


def test_unentered_trade_expires_at_last_allowed_candle() -> None:
    trade = simulate_trade(
        _signal(),
        (
            _candle(high=99.0, low=98.5, close=99.0, open_price=99.0, index=0),
            _candle(high=99.5, low=98.5, close=99.2, open_price=99.0, index=1),
        ),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0, maximum_holding_candles=2),
    )

    assert trade.outcome is BacktestOutcome.MISSED_ENTRY
    assert trade.holding_candles == 2


def test_simulated_trade_preserves_reproducibility_metadata() -> None:
    trade = simulate_trade(
        _signal(),
        (_candle(high=105.0, low=99.0),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
        metadata={
            "entry_state": "READY_NOW",
            "scanner_type": "NORMAL_MARKET",
            "precision_entry_score": 82.5,
        },
    )

    assert trade.metadata["entry_state"] == "READY_NOW"
    assert trade.metadata["precision_entry_score"] == pytest.approx(82.5)


def test_historical_runner_uses_only_future_candles_without_lookahead() -> None:
    signal = _signal()
    request = BacktestRequest(
        signals=(signal,),
        candles_by_symbol={
            "BTC/USDT": (
                _candle(high=110.0, low=97.0, index=-1),
                _candle(high=103.0, low=99.0, close=101.0, index=0),
                _candle(high=105.0, low=100.0, close=104.0, index=1),
            )
        },
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
        dataset_id="unit",
        code_version="test",
    )

    study = HistoricalBacktestRunner().run(request)

    assert study.report.total_trades == 1
    assert study.report.trades[0].outcome is BacktestOutcome.TARGET
    assert study.report.trades[0].holding_candles == 2
    assert study.skipped_signal_count == 0
    assert len(study.dataset_hash) == 64
    assert len(study.config_hash) == 64
    assert len(study.code_hash) == 64


def test_historical_runner_skips_signal_without_future_data() -> None:
    signal = _signal()
    request = BacktestRequest(
        signals=(signal,),
        candles_by_symbol={"BTC/USDT": (_candle(high=110.0, low=97.0, index=-1),)},
        dataset_id="unit",
    )

    study = HistoricalBacktestRunner().run(request)

    assert study.generated_signal_count == 1
    assert study.simulated_trade_count == 0
    assert study.skipped_signal_count == 1
    assert study.report.total_trades == 0


def test_backtest_request_requires_chronological_signals() -> None:
    later = _signal()
    earlier = BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=NOW - timedelta(minutes=5),
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=10.0,
        risk_amount=20.0,
        confidence_score=80.0,
    )

    with pytest.raises(ValueError, match="chronological"):
        BacktestRequest(
            signals=(later, earlier),
            candles_by_symbol={"BTC/USDT": ()},
        )
