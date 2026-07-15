from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from apex.backtesting import BacktestSignal
from apex.domain.models import Candle
from apex.paper_trading import (
    PaperTrade,
    PaperTradeState,
    PaperTradeStore,
    run_provider_backed_paper_cycle,
)
from apex.strategies import StrategyType, TradeDirection


class _Provider:
    def __init__(self, candles: dict[str, tuple[Candle, ...]], failing: set[str] | None = None) -> None:
        self.candles = candles
        self.failing = failing or set()
        self.calls: list[str] = []

    def fetch_candles(self, symbol: str, timeframe: str, *, limit: int) -> tuple[Candle, ...]:
        self.calls.append(symbol)
        assert timeframe == "5m"
        assert limit == 20
        if symbol in self.failing:
            raise ValueError("provider failure")
        return self.candles.get(symbol, ())


def _trade(trade_id: str, symbol: str, market_type: str, now: datetime) -> PaperTrade:
    signal = BacktestSignal(
        symbol=symbol,
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=now,
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
        created_at=now,
        updated_at=now,
        analysis_payload={"market_type": market_type},
        lifecycle_events=(
            {"event_type": "SETUP_GENERATED", "occurred_at": now.isoformat()},
            {"event_type": "WAITING_FOR_ENTRY", "occurred_at": now.isoformat()},
        ),
    )


def _candle(symbol: str, now: datetime) -> Candle:
    return Candle(
        symbol=symbol,
        timeframe="5m",
        open_time=now,
        close_time=now + timedelta(minutes=5),
        open=101.0,
        high=102.0,
        low=99.0,
        close=100.5,
        volume=10.0,
        is_closed=True,
        source="test",
    )


def test_runtime_fetches_each_active_matching_symbol_once(tmp_path: Path) -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    store = PaperTradeStore(tmp_path / "trades.json")
    store.save(
        (
            _trade("btc-1", "BTCUSDT", "futures", now),
            _trade("btc-2", "BTCUSDT", "futures", now),
            _trade("eth-spot", "ETHUSDT", "spot", now),
        )
    )
    provider = _Provider({"BTCUSDT": (_candle("BTCUSDT", now),)})

    result = run_provider_backed_paper_cycle(
        store=store,
        provider=provider,
        market_type="futures",
        timeframe="5m",
        candle_limit=20,
        started_at=now,
        completed_at=now + timedelta(minutes=5),
    )

    assert provider.calls == ["BTCUSDT"]
    assert result.requested_symbols == ("BTCUSDT",)
    assert result.successful_symbols == ("BTCUSDT",)
    assert result.fully_collected
    assert result.cycle.eligible_trade_count == 2


def test_runtime_isolates_provider_failure_and_preserves_trade(tmp_path: Path) -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    trade = _trade("btc", "BTCUSDT", "futures", now)
    store = PaperTradeStore(tmp_path / "trades.json")
    store.save((trade,))
    provider = _Provider({}, failing={"BTCUSDT"})

    result = run_provider_backed_paper_cycle(
        store=store,
        provider=provider,
        market_type="futures",
        timeframe="5m",
        candle_limit=20,
        started_at=now,
    )

    assert result.provider_failures == (("BTCUSDT", "provider failure"),)
    assert not result.fully_collected
    assert result.cycle.missing_candle_trade_ids == ("btc",)
    assert store.load() == (trade,)
