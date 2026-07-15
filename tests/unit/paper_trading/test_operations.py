from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from apex.backtesting import BacktestSignal
from apex.domain.models import Candle
from apex.paper_trading import (
    PaperTrade,
    PaperTradeState,
    PaperTradeStore,
    run_paper_operation_cycle,
)
from apex.strategies import StrategyType, TradeDirection


def _trade(trade_id: str, *, market_type: str, created_at: datetime) -> PaperTrade:
    signal = BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=created_at,
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
        quantity=1.0,
        risk_amount=5.0,
        confidence_score=80.0,
    )
    return PaperTrade(
        trade_id=trade_id,
        signal=signal,
        state=PaperTradeState.WAITING_FOR_ENTRY,
        created_at=created_at,
        updated_at=created_at,
        analysis_payload={"market_type": market_type},
        lifecycle_events=(
            {"event_type": "SETUP_GENERATED", "occurred_at": created_at.isoformat()},
            {"event_type": "WAITING_FOR_ENTRY", "occurred_at": created_at.isoformat()},
        ),
    )


def _candle(now: datetime) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="1m",
        open_time=now,
        close_time=now + timedelta(minutes=1),
        open=101.0,
        high=102.0,
        low=99.0,
        close=100.5,
        volume=10.0,
        is_closed=True,
        source="test",
    )


def test_cycle_advances_only_matching_market_and_writes_daily_report(tmp_path: Path) -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    store = PaperTradeStore(tmp_path / "trades.json")
    store.save(
        (
            _trade("futures-trade", market_type="futures", created_at=now),
            _trade("spot-trade", market_type="spot", created_at=now),
        )
    )
    report_path = tmp_path / "daily.json"

    result = run_paper_operation_cycle(
        store=store,
        candles_by_symbol={"BTCUSDT": (_candle(now),)},
        market_type="futures",
        started_at=now,
        completed_at=now + timedelta(minutes=1),
        daily_report_date=date(2026, 7, 15),
        daily_report_path=report_path,
    )

    trades = {trade.trade_id: trade for trade in store.load()}
    assert result.loaded_trade_count == 2
    assert result.eligible_trade_count == 1
    assert result.advanced_trade_count == 1
    assert result.unchanged_trade_count == 0
    assert result.trade_ids == ("futures-trade",)
    assert trades["futures-trade"].state is PaperTradeState.ENTERED
    assert trades["spot-trade"].state is PaperTradeState.WAITING_FOR_ENTRY
    assert result.daily_report is not None
    assert report_path.exists()


def test_cycle_reports_missing_closed_candles_without_modifying_trade(tmp_path: Path) -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    trade = _trade("spot-trade", market_type="spot", created_at=now)
    store = PaperTradeStore(tmp_path / "trades.json")
    store.save((trade,))

    result = run_paper_operation_cycle(
        store=store,
        candles_by_symbol={},
        market_type="spot",
        started_at=now,
    )

    assert result.advanced_trade_count == 0
    assert result.unchanged_trade_count == 1
    assert result.missing_candle_trade_ids == ("spot-trade",)
    assert store.load() == (trade,)


def test_cycle_is_deterministic_for_equivalent_candle_order(tmp_path: Path) -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    first_candle = _candle(now)
    second_candle = Candle(
        **{
            **first_candle.model_dump(),
            "open_time": now + timedelta(minutes=1),
            "close_time": now + timedelta(minutes=2),
            "open": 100.5,
            "high": 103.0,
            "low": 100.0,
            "close": 102.0,
        }
    )
    results = []
    for index, candles in enumerate(((first_candle, second_candle), (second_candle, first_candle))):
        store = PaperTradeStore(tmp_path / f"trades-{index}.json")
        store.save((_trade("trade", market_type="futures", created_at=now),))
        result = run_paper_operation_cycle(
            store=store,
            candles_by_symbol={"BTCUSDT": candles},
            market_type="futures",
            started_at=now,
            completed_at=now + timedelta(minutes=2),
        )
        results.append((result, store.load()))

    assert results[0] == results[1]
