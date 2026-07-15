from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.application.analysis import (
    build_strategy_context,
    load_symbols,
    scan_symbols,
    serialize_scan_result,
)
from apex.domain import Candle, GainerStateThresholds
from apex.domain.models import (
    ExchangeFilterSnapshot,
    LiquidationCluster,
    LiquidationClusterSide,
    LiquidationClusterSnapshot,
    OrderBookLevel,
    OrderBookSnapshot,
    TickerSnapshot,
)
from apex.strategies import TimeframeRole

NOW = datetime(2026, 7, 13, tzinfo=UTC)


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, int]] = []

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        if symbol == "BROKEN/USDT":
            raise RuntimeError("fixture failure")
        self.requests.append((symbol, timeframe, limit))
        candles: list[Candle] = []
        start = NOW - timedelta(minutes=limit)
        for index in range(limit):
            base = 100.0 + index * 0.05
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=start + timedelta(minutes=index),
                    close_time=start + timedelta(minutes=index + 1),
                    open=base,
                    high=base + 1.5,
                    low=base - 1.0,
                    close=base + 0.5,
                    volume=100.0 + index,
                    is_closed=True,
                    source="fixture",
                )
            )
        return candles

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        raise NotImplementedError(f"ticker unavailable for {symbol}")


class ActiveFinalProvider(FakeProvider):
    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        candles = super().fetch_candles(symbol, timeframe, limit)
        final = candles[-1]
        candles[-1] = Candle(
            symbol=final.symbol,
            timeframe=final.timeframe,
            open_time=final.open_time,
            close_time=final.close_time,
            open=final.open,
            high=final.high + 1.0,
            low=final.low,
            close=final.close + 2.0,
            volume=final.volume,
            is_closed=False,
            source=final.source,
        )
        return candles


class TickerProvider(FakeProvider):
    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        return TickerSnapshot(
            symbol=symbol,
            last_price=123.45,
            bid_price=123.40,
            ask_price=123.50,
            quote_volume_24h=1_000_000.0,
            captured_at=NOW,
            source="fixture",
        )

    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        return OrderBookSnapshot(
            symbol=symbol,
            bids=(OrderBookLevel(price=123.40, quantity=10.0),),
            asks=(OrderBookLevel(price=123.50, quantity=5.0),),
            captured_at=NOW,
            source="fixture",
        )

    def fetch_exchange_filters(self, symbol: str) -> ExchangeFilterSnapshot:
        return ExchangeFilterSnapshot(
            symbol=symbol,
            tick_size=0.01,
            step_size=0.001,
            min_quantity=0.001,
            min_notional=5.0,
            captured_at=NOW,
            source="fixture",
        )

    def fetch_liquidation_clusters(self, symbol: str) -> LiquidationClusterSnapshot:
        return LiquidationClusterSnapshot(
            symbol=symbol,
            clusters=(
                LiquidationCluster(
                    side=LiquidationClusterSide.LONG,
                    price=123.00,
                    notional=500_000.0,
                ),
                LiquidationCluster(
                    side=LiquidationClusterSide.SHORT,
                    price=124.00,
                    notional=750_000.0,
                ),
            ),
            captured_at=NOW,
            source="fixture",
        )


def test_load_symbols_validates_config(tmp_path: Path) -> None:
    path = tmp_path / "symbols.yaml"
    path.write_text("symbols:\n  - BTC/USDT\n  - ETH/USDT\n", encoding="utf-8")

    assert load_symbols(path) == ("BTC/USDT", "ETH/USDT")


def test_load_symbols_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "symbols.yaml"
    path.write_text("symbols:\n  - BTC/USDT\n  - BTC/USDT\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate"):
        load_symbols(path)


def test_scan_isolates_symbol_failures() -> None:
    result = scan_symbols(
        ("BTC/USDT", "BROKEN/USDT"),
        FakeProvider(),
        timeframes=("5m",),
        candle_limit=200,
        generated_at=NOW,
    )

    payload = serialize_scan_result(result)

    assert "BROKEN/USDT" in payload["failures"]
    assert payload["results"]
    assert payload["generated_at"] == NOW.isoformat()
    assert "timeframe_data_quality" in payload["results"][0]
    assert "5m" in payload["results"][0]["timeframe_data_quality"]
    assert "current_price_source" in payload["results"][0]["timeframe_data_quality"]["5m"]


def test_scan_all_mode_preserves_normal_and_gainer_paths() -> None:
    result = scan_symbols(
        ("BTC/USDT",),
        FakeProvider(),
        timeframes=("5m",),
        candle_limit=200,
        generated_at=NOW,
        scanner_mode="all",
    )

    payload = serialize_scan_result(result)

    assert payload["scanner_mode"] == "all"
    assert {item["scanner_type"] for item in payload["results"]} == {
        "NORMAL_MARKET",
        "GAINER",
    }
    assert any(item["gainer_state"] is not None for item in payload["results"])
    normal = next(item for item in payload["results"] if item["scanner_type"] == "NORMAL_MARKET")
    gainer = next(item for item in payload["results"] if item["scanner_type"] == "GAINER")
    assert "range_reversal" in normal["strategy_routing"]["enabled_strategies"]
    assert "range_reversal" in gainer["strategy_routing"]["disabled_strategies"]


def test_scan_uses_configured_strategy_routing() -> None:
    result = scan_symbols(
        ("BTC/USDT",),
        FakeProvider(),
        timeframes=("5m",),
        candle_limit=200,
        generated_at=NOW,
        scanner_mode="all",
        strategy_routing={
            "normal_market": ["trend_pullback"],
            "gainer": ["range_reversal"],
        },
    )

    payload = serialize_scan_result(result)
    normal = next(item for item in payload["results"] if item["scanner_type"] == "NORMAL_MARKET")
    gainer = next(item for item in payload["results"] if item["scanner_type"] == "GAINER")

    assert normal["strategy_routing"]["route_key"] == "normal_market"
    assert normal["strategy_routing"]["enabled_strategies"] == ["trend_pullback"]
    assert "range_reversal" in normal["strategy_routing"]["disabled_strategies"]
    assert gainer["strategy_routing"]["route_key"] == "gainer"
    assert gainer["strategy_routing"]["enabled_strategies"] == ["range_reversal"]
    assert "momentum_gainer_continuation" in gainer["strategy_routing"]["disabled_strategies"]


def test_scan_uses_configured_gainer_state_thresholds() -> None:
    result = scan_symbols(
        ("BTC/USDT",),
        FakeProvider(),
        timeframes=("5m",),
        candle_limit=200,
        generated_at=NOW,
        scanner_mode="gainers",
        gainer_state_thresholds=GainerStateThresholds(fresh_total_return_pct=100.0),
    )

    payload = serialize_scan_result(result)

    assert payload["results"][0]["gainer_state"] == "CHAOTIC"


def test_strategy_context_uses_configured_timeframe_roles() -> None:
    provider = FakeProvider()

    context, regimes = build_strategy_context(
        "BTC/USDT",
        provider,
        timeframes=("5m", "1D"),
        candle_limit=200,
        timeframe_roles={"1D": "long_term_macro", "5m": "entry"},
    )

    assert provider.requests == [("BTC/USDT", "5m", 200), ("BTC/USDT", "1D", 200)]
    assert [frame.timeframe for frame in context.frames] == ["1D", "5m"]
    assert [frame.role for frame in context.frames] == [
        TimeframeRole.LONG_TERM_MACRO,
        TimeframeRole.ENTRY,
    ]
    assert set(regimes) == {"1D", "5m"}


def test_strategy_context_exposes_closed_active_and_staleness_prices() -> None:
    context, _regimes = build_strategy_context(
        "BTC/USDT",
        ActiveFinalProvider(),
        timeframes=("5m",),
        candle_limit=201,
        timeframe_roles={"5m": "entry"},
        timeframe_max_staleness_seconds={"5m": 60},
        received_at=NOW + timedelta(minutes=10),
    )

    frame = context.frames[0]

    assert frame.current_price == frame.active_candle_price
    assert frame.current_price_source == "active_candle_price"
    assert frame.analysis_price == frame.latest_closed_price
    assert frame.active_candle_price is not None
    assert frame.latest_closed_price is not None
    assert frame.active_candle_price > frame.latest_closed_price
    assert frame.last_closed_at is not None
    assert frame.last_received_at == NOW + timedelta(minutes=10)
    assert frame.staleness_seconds is not None
    assert frame.staleness_seconds > 60
    assert frame.is_stale is True
    assert frame.data_confidence == 0.5


def test_strategy_context_prefers_ticker_price_for_current_price() -> None:
    context, _regimes = build_strategy_context(
        "BTC/USDT",
        TickerProvider(),
        timeframes=("5m",),
        candle_limit=200,
        timeframe_roles={"5m": "entry"},
        received_at=NOW,
    )

    frame = context.frames[0]

    assert frame.current_price == 123.45
    assert frame.ticker_price == 123.45
    assert frame.spread_percentage == pytest.approx((0.10 / 123.45) * 100)
    assert frame.order_book_depth_imbalance is not None
    assert frame.order_book_depth_imbalance > 0
    assert frame.exchange_tick_size == 0.01
    assert frame.exchange_step_size == 0.001
    assert frame.exchange_min_notional == 5.0
    assert frame.nearest_long_cluster_distance_pct is not None
    assert frame.nearest_short_cluster_distance_pct is not None
    assert frame.current_price_source == "ticker_price"
    assert frame.analysis_price == frame.latest_closed_price
