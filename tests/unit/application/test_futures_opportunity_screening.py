"""Step 7 tests for candle-aware futures opportunity screening."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.application.futures_screening import (
    classify_discovery_lanes,
    extract_opportunity_features,
    score_futures_opportunity,
    screen_futures_universe,
    ticker_prefilter_symbols,
)
from apex.domain.futures_market import FuturesContractMetadata
from apex.domain.futures_screening import (
    FuturesDiscoveryLane,
    FuturesScreenerConfig,
    FuturesScreeningExclusionReason,
    FuturesTickerSnapshot,
)
from apex.domain.models import Candle


def _contract(exchange_symbol: str) -> FuturesContractMetadata:
    base_asset = exchange_symbol.removesuffix("USDT")
    return FuturesContractMetadata(
        symbol=f"{base_asset}/USDT",
        exchange_symbol=exchange_symbol,
        base_asset=base_asset,
        quote_asset="USDT",
        status="TRADING",
        contract_type="PERPETUAL",
        tick_size=0.01,
        step_size=0.001,
        minimum_quantity=0.001,
        minimum_notional=5.0,
    )


def _ticker(
    exchange_symbol: str,
    *,
    movement: float = 5.0,
    volume: float = 50_000_000.0,
    bid: float = 100.0,
    ask: float = 100.05,
) -> FuturesTickerSnapshot:
    return FuturesTickerSnapshot(
        symbol=exchange_symbol,
        exchange_symbol=exchange_symbol,
        last_price=(bid + ask) / 2,
        bid_price=bid,
        ask_price=ask,
        quote_volume_24h=volume,
        price_change_percentage_24h=movement,
        captured_at=datetime.now(UTC),
        source="test",
    )


def _candles(
    exchange_symbol: str,
    *,
    start_price: float = 100.0,
    step: float = 0.2,
    volume_start: float = 1_000.0,
    volume_step: float = 20.0,
    count: int = 49,
    wick: float = 0.05,
) -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    price = start_price
    for index in range(count):
        open_price = price
        close_price = price + step
        high = max(open_price, close_price) + wick
        low = min(open_price, close_price) - wick
        open_time = start + timedelta(minutes=5 * index)
        candles.append(
            Candle(
                symbol=exchange_symbol,
                timeframe="5m",
                open_time=open_time,
                close_time=open_time + timedelta(minutes=5),
                open=open_price,
                high=high,
                low=low,
                close=close_price,
                volume=volume_start + volume_step * index,
                is_closed=True,
                source="test",
            )
        )
        price = close_price
    return tuple(candles)


def test_extract_opportunity_features_derives_recent_windows() -> None:
    features = extract_opportunity_features(_candles("AAAUSDT"))

    assert features.return_5m_pct > 0
    assert features.return_15m_pct > features.return_5m_pct
    assert features.return_30m_pct > features.return_15m_pct
    assert features.return_1h_pct > features.return_30m_pct
    assert features.relative_volume > 1
    assert features.volume_acceleration > 1
    assert features.atr_percentage > 0
    assert 0 <= features.breakout_proximity <= 1
    assert 0 <= features.directional_persistence <= 1


def test_opportunity_score_rewards_acceleration_and_participation() -> None:
    config = FuturesScreenerConfig(
        shortlist_size=1,
        ticker_prefilter_size=2,
    )
    active_features = extract_opportunity_features(
        _candles(
            "AAAUSDT",
            step=0.5,
            volume_step=100.0,
            wick=0.02,
        )
    )
    quiet_features = extract_opportunity_features(
        _candles(
            "BBBUSDT",
            step=0.02,
            volume_step=0.0,
            wick=0.08,
        )
    )

    active = score_futures_opportunity(
        _ticker("AAAUSDT", movement=8.0),
        active_features,
        config,
    )
    quiet = score_futures_opportunity(
        _ticker("BBBUSDT", movement=2.0),
        quiet_features,
        config,
    )

    assert active.total > quiet.total
    assert active.acceleration > quiet.acceleration
    assert active.directional_clarity >= quiet.directional_clarity


def test_candle_aware_screening_ranks_by_opportunity_score() -> None:
    contracts = (_contract("AAAUSDT"), _contract("BBBUSDT"))
    tickers = (
        _ticker("AAAUSDT", movement=6.0),
        _ticker("BBBUSDT", movement=6.0),
    )
    candle_sets = {
        "AAAUSDT": _candles(
            "AAAUSDT",
            step=0.5,
            volume_step=120.0,
            wick=0.02,
        ),
        "BBBUSDT": _candles(
            "BBBUSDT",
            step=0.03,
            volume_step=0.0,
            wick=0.12,
        ),
    }

    result = screen_futures_universe(
        contracts,
        tickers,
        candle_sets,
        FuturesScreenerConfig(
            shortlist_size=2,
            ticker_prefilter_size=2,
        ),
    )

    assert [candidate.contract.exchange_symbol for candidate in result.candidates] == [
        "AAAUSDT",
        "BBBUSDT",
    ]
    assert result.candidates[0].opportunity.total > result.candidates[1].opportunity.total
    assert result.candidates[0].discovery_lanes
    assert result.hard_eligible_count == 2
    assert result.candle_screened_count == 2


def test_discovery_lanes_explain_shortlist_route() -> None:
    config = FuturesScreenerConfig(shortlist_size=1, ticker_prefilter_size=1)
    features = extract_opportunity_features(
        _candles(
            "AAAUSDT",
            step=0.6,
            volume_step=150.0,
            wick=0.02,
        )
    )
    opportunity = score_futures_opportunity(
        _ticker("AAAUSDT", movement=9.0),
        features,
        config,
    )

    lanes = classify_discovery_lanes(_ticker("AAAUSDT", movement=9.0), features, opportunity)

    assert {item.lane for item in lanes} & {
        FuturesDiscoveryLane.TREND_CONTINUATION,
        FuturesDiscoveryLane.FAST_MOVER,
        FuturesDiscoveryLane.RELATIVE_STRENGTH_WEAKNESS,
    }
    assert all(item.reason for item in lanes)


def test_relative_strength_lane_uses_benchmark_return_when_available() -> None:
    config = FuturesScreenerConfig(shortlist_size=1, ticker_prefilter_size=1)
    features = extract_opportunity_features(_candles("AAAUSDT", step=0.3))
    opportunity = score_futures_opportunity(_ticker("AAAUSDT"), features, config)

    aligned = classify_discovery_lanes(
        _ticker("AAAUSDT"),
        features,
        opportunity,
        benchmark_return_1h_pct=features.return_1h_pct - 0.25,
    )
    divergent = classify_discovery_lanes(
        _ticker("AAAUSDT"),
        features,
        opportunity,
        benchmark_return_1h_pct=0.0,
    )

    assert not any(item.lane is FuturesDiscoveryLane.RELATIVE_STRENGTH_WEAKNESS for item in aligned)
    assert any(item.lane is FuturesDiscoveryLane.RELATIVE_STRENGTH_WEAKNESS for item in divergent)


def test_ticker_prefilter_reserves_space_for_quiet_liquid_market() -> None:
    contracts = tuple(_contract(f"C{index}USDT") for index in range(8))
    tickers = tuple(
        _ticker(
            f"C{index}USDT",
            movement=0.1 if index == 0 else float(index + 3),
            volume=500_000_000.0 if index == 0 else 50_000_000.0,
        )
        for index in range(8)
    )

    selected = ticker_prefilter_symbols(
        contracts,
        tickers,
        FuturesScreenerConfig(shortlist_size=3, ticker_prefilter_size=5),
    )

    assert "C0USDT" in selected


def test_candle_aware_screening_records_fetch_failure() -> None:
    result = screen_futures_universe(
        (_contract("AAAUSDT"),),
        (_ticker("AAAUSDT"),),
        {},
        FuturesScreenerConfig(
            shortlist_size=1,
            ticker_prefilter_size=1,
        ),
        candle_failures={"AAAUSDT": "provider unavailable"},
    )

    assert result.candidates == ()
    assert result.candle_screened_count == 0
    assert result.exclusions[0].reason == (FuturesScreeningExclusionReason.CANDLE_FETCH_FAILED)
    assert "provider unavailable" in result.exclusions[0].detail


def test_candle_aware_screening_records_insufficient_history() -> None:
    result = screen_futures_universe(
        (_contract("AAAUSDT"),),
        (_ticker("AAAUSDT"),),
        {"AAAUSDT": _candles("AAAUSDT", count=20)},
        FuturesScreenerConfig(
            shortlist_size=1,
            ticker_prefilter_size=1,
            minimum_candle_count=25,
        ),
    )

    assert result.candidates == ()
    assert result.exclusions[0].reason == (
        FuturesScreeningExclusionReason.INSUFFICIENT_CANDLE_HISTORY
    )


def test_candle_aware_screening_uses_symbol_as_final_tiebreaker() -> None:
    contracts = (_contract("BBBUSDT"), _contract("AAAUSDT"))
    tickers = (_ticker("BBBUSDT"), _ticker("AAAUSDT"))
    same = _candles("AAAUSDT")

    result = screen_futures_universe(
        contracts,
        tickers,
        {
            "AAAUSDT": same,
            "BBBUSDT": tuple(candle.model_copy(update={"symbol": "BBBUSDT"}) for candle in same),
        },
        FuturesScreenerConfig(
            shortlist_size=2,
            ticker_prefilter_size=2,
        ),
    )

    assert [candidate.contract.exchange_symbol for candidate in result.candidates] == [
        "AAAUSDT",
        "BBBUSDT",
    ]
