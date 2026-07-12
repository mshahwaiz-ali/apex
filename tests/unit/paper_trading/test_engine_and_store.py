from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting import BacktestConfig, BacktestSignal, simulate_trade, summarize_trades
from apex.domain import Candle
from apex.paper_trading import (
    PaperTrade,
    PaperTradeConfig,
    PaperTradeState,
    PaperTradeStore,
    compare_backtest_to_paper,
    generate_paper_report,
    summarize_paper_trades,
    update_paper_trade,
)
from apex.strategies import StrategyType, TradeDirection

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _signal() -> BacktestSignal:
    return BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=NOW,
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=10.0,
        risk_amount=20.0,
        confidence_score=80.0,
    )


def _trade() -> PaperTrade:
    return PaperTrade(
        trade_id="paper-1",
        signal=_signal(),
        state=PaperTradeState.WAITING_FOR_ENTRY,
        created_at=NOW,
        updated_at=NOW,
        analysis_payload={"symbol": "BTC/USDT"},
    )


def _candle(
    *,
    high: float,
    low: float,
    close: float,
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


def test_waiting_trade_enters_then_hits_target() -> None:
    entered = update_paper_trade(
        _trade(),
        (_candle(high=101.0, low=99.0, close=100.5),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    closed = update_paper_trade(
        entered,
        (_candle(high=105.0, low=100.0, close=104.0, index=1),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert entered.state is PaperTradeState.ENTERED
    assert closed.state is PaperTradeState.TARGET_HIT
    assert closed.net_pnl == pytest.approx(40.0)
    assert closed.realized_r_multiple == pytest.approx(2.0)


def test_target_before_entry_expires_trade() -> None:
    result = update_paper_trade(
        _trade(),
        (_candle(high=105.0, low=101.0, close=104.0, open_price=103.0),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert result.state is PaperTradeState.EXPIRED
    assert "target reached before entry" in result.notes


def test_entry_timeout_expires_flat() -> None:
    result = update_paper_trade(
        _trade(),
        (
            _candle(high=99.5, low=98.5, close=99.0, open_price=99.0, index=0),
            _candle(high=99.5, low=98.5, close=99.0, open_price=99.0, index=1),
        ),
        config=PaperTradeConfig(
            entry_timeout_candles=2,
            fee_pct=0.0,
            slippage_pct=0.0,
        ),
    )

    assert result.state is PaperTradeState.EXPIRED
    assert result.net_pnl == pytest.approx(0.0)


def test_paper_summary_and_store_roundtrip(tmp_path) -> None:
    closed = update_paper_trade(
        update_paper_trade(
            _trade(),
            (_candle(high=101.0, low=99.0, close=100.5),),
            config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
        ),
        (_candle(high=105.0, low=100.0, close=104.0, index=1),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    store = PaperTradeStore(tmp_path / "paper.json")
    store.save((closed,))

    loaded = store.load()
    performance = summarize_paper_trades(loaded)

    assert loaded == (closed,)
    assert performance.total_trades == 1
    assert performance.closed_trades == 1
    assert performance.win_rate == pytest.approx(1.0)


def test_paper_report_and_backtest_comparison() -> None:
    closed = update_paper_trade(
        update_paper_trade(
            _trade(),
            (_candle(high=101.0, low=99.0, close=100.5),),
            config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
        ),
        (_candle(high=105.0, low=100.0, close=104.0, index=1),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    paper = summarize_paper_trades((closed,))
    backtest_trade = simulate_trade(
        _signal(),
        (_candle(high=105.0, low=99.0, close=104.0),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    backtest = summarize_trades((backtest_trade,))

    report = generate_paper_report((closed,), period="daily", generated_at=NOW)
    comparison = compare_backtest_to_paper(backtest, paper, generated_at=NOW)

    assert report.performance == paper
    assert report.notes == ("closed_trades=1", "open_trades=0")
    assert comparison.backtest_total_trades == 1
    assert comparison.paper_total_trades == 1
    assert comparison.win_rate_delta == pytest.approx(0.0)
