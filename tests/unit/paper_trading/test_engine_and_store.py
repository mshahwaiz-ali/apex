from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.backtesting import BacktestConfig, BacktestSignal, simulate_trade, summarize_trades
from apex.domain import Candle, TradeLifecycleState
from apex.paper_trading import (
    PaperTrade,
    PaperTradeConfig,
    PaperTradeState,
    PaperTradeStore,
    build_paper_replay_report,
    compare_backtest_to_paper,
    generate_paper_report,
    paper_lifecycle_snapshot,
    summarize_paper_trades,
    update_paper_trade,
)
from apex.strategies import StrategyType, TradeDirection

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _signal(
    *,
    target_prices: tuple[float, ...] = (),
    partial_close_percentages: tuple[float, ...] = (),
) -> BacktestSignal:
    return BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=NOW,
        entry_price=100.0,
        stop_price=98.0,
        target_price=target_prices[0] if target_prices else 104.0,
        quantity=10.0,
        risk_amount=20.0,
        confidence_score=80.0,
        target_prices=target_prices,
        partial_close_percentages=partial_close_percentages,
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


def _partial_trade() -> PaperTrade:
    return PaperTrade(
        trade_id="paper-partial",
        signal=_signal(
            target_prices=(102.0, 104.0),
            partial_close_percentages=(50.0, 50.0),
        ),
        state=PaperTradeState.WAITING_FOR_ENTRY,
        created_at=NOW,
        updated_at=NOW,
        analysis_payload={"symbol": "BTC/USDT"},
        lifecycle_events=(
            {
                "event_type": "SETUP_GENERATED",
                "occurred_at": NOW.isoformat(),
                "reason": None,
            },
            {
                "event_type": "WAITING_FOR_ENTRY",
                "occurred_at": NOW.isoformat(),
                "reason": None,
            },
        ),
    )


def _trade_with_plan() -> PaperTrade:
    return PaperTrade(
        trade_id="paper-1",
        signal=_signal(),
        state=PaperTradeState.WAITING_FOR_ENTRY,
        created_at=NOW,
        updated_at=NOW,
        analysis_payload={"symbol": "BTC/USDT"},
        futures_plan={"status": "APPROVED", "position": {"leverage": 20.0}},
        lifecycle_events=(
            {
                "event_type": "SETUP_GENERATED",
                "occurred_at": NOW.isoformat(),
                "reason": None,
            },
            {
                "event_type": "WAITING_FOR_ENTRY",
                "occurred_at": NOW.isoformat(),
                "reason": None,
            },
        ),
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


def test_paper_trade_realizes_partial_target_then_stop() -> None:
    entered = update_paper_trade(
        _partial_trade(),
        (_candle(high=101.0, low=99.0, close=100.5),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    partial = update_paper_trade(
        entered,
        (_candle(high=102.5, low=99.0, close=102.0, index=1),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    closed = update_paper_trade(
        partial,
        (_candle(high=101.0, low=97.5, close=98.0, index=2),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert partial.state is PaperTradeState.PARTIALLY_CLOSED
    assert partial.net_pnl == pytest.approx(10.0)
    assert partial.partial_target_count == 1
    assert partial.closed_percentage == pytest.approx(50.0)
    assert closed.state is PaperTradeState.STOPPED
    assert closed.net_pnl == pytest.approx(0.0)
    assert closed.closed_percentage == pytest.approx(100.0)


def test_paper_trade_completes_target_ladder_and_replays_lifecycle() -> None:
    closed = update_paper_trade(
        update_paper_trade(
            _partial_trade(),
            (_candle(high=101.0, low=99.0, close=100.5),),
            config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
        ),
        (_candle(high=104.5, low=99.0, close=104.0, index=1),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    lifecycle = paper_lifecycle_snapshot(closed)

    assert closed.state is PaperTradeState.TARGET_HIT
    assert closed.net_pnl == pytest.approx(30.0)
    assert closed.partial_target_count == 2
    assert closed.closed_percentage == pytest.approx(100.0)
    assert [event["event_type"] for event in closed.lifecycle_events] == [
        "SETUP_GENERATED",
        "WAITING_FOR_ENTRY",
        "ENTRY_FILLED",
        "PARTIAL_TARGET_HIT",
        "FULL_TARGET_HIT",
    ]
    assert lifecycle.state is TradeLifecycleState.TARGET_HIT
    assert lifecycle.partial_targets_hit == ("tp1",)
    assert lifecycle.last_target_label == "tp2"


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


def test_paper_summary_and_store_roundtrip(tmp_path: Path) -> None:
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


def test_paper_store_roundtrips_futures_plan_and_lifecycle_events(
    tmp_path: Path,
) -> None:
    trade = _trade_with_plan()
    store = PaperTradeStore(tmp_path / "paper.json")
    store.save((trade,))

    loaded = store.load()

    assert loaded == (trade,)
    assert loaded[0].futures_plan == trade.futures_plan
    assert loaded[0].lifecycle_events == trade.lifecycle_events


def test_paper_store_roundtrips_target_ladder_and_partial_progress(
    tmp_path: Path,
) -> None:
    partial = update_paper_trade(
        update_paper_trade(
            _partial_trade(),
            (_candle(high=101.0, low=99.0, close=100.5),),
            config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
        ),
        (_candle(high=102.5, low=99.0, close=102.0, index=1),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    store = PaperTradeStore(tmp_path / "paper.json")
    store.save((partial,))

    loaded = store.load()

    assert loaded == (partial,)
    assert loaded[0].signal.target_prices == (102.0, 104.0)
    assert loaded[0].signal.partial_close_percentages == (50.0, 50.0)
    assert loaded[0].partial_target_count == 1
    assert loaded[0].closed_percentage == pytest.approx(50.0)


def test_paper_updates_append_replayable_lifecycle_events() -> None:
    entered = update_paper_trade(
        _trade_with_plan(),
        (_candle(high=101.0, low=99.0, close=100.5),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    closed = update_paper_trade(
        entered,
        (_candle(high=105.0, low=100.0, close=104.0, index=1),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    lifecycle = paper_lifecycle_snapshot(closed)

    assert [event["event_type"] for event in closed.lifecycle_events] == [
        "SETUP_GENERATED",
        "WAITING_FOR_ENTRY",
        "ENTRY_FILLED",
        "FULL_TARGET_HIT",
    ]
    assert lifecycle.state is TradeLifecycleState.TARGET_HIT
    assert lifecycle.closed_percentage == 100


def test_paper_replay_report_summarizes_lifecycle_snapshots() -> None:
    closed = update_paper_trade(
        update_paper_trade(
            _trade_with_plan(),
            (_candle(high=101.0, low=99.0, close=100.5),),
            config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
        ),
        (_candle(high=105.0, low=100.0, close=104.0, index=1),),
        config=PaperTradeConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    report = build_paper_replay_report((closed,), generated_at=NOW)

    assert report["trade_count"] == 1
    assert report["replayed_count"] == 1
    assert report["failure_count"] == 0
    assert report["trades"][0]["trade_id"] == closed.trade_id
    assert report["trades"][0]["lifecycle_state"] == "TARGET_HIT"
    assert report["trades"][0]["event_count"] == 4


def test_paper_replay_report_records_replay_failures() -> None:
    broken = PaperTrade(
        trade_id="broken",
        signal=_signal(),
        state=PaperTradeState.WAITING_FOR_ENTRY,
        created_at=NOW,
        updated_at=NOW,
        analysis_payload={},
        lifecycle_events=(
            {
                "event_type": "PARTIAL_TARGET_HIT",
                "occurred_at": NOW.isoformat(),
                "closed_percentage": 50,
            },
        ),
    )

    report = build_paper_replay_report((broken,), generated_at=NOW)

    assert report["replayed_count"] == 0
    assert report["failure_count"] == 1
    assert "broken" in report["failures"]


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
