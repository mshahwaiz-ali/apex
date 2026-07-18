"""Resolve symbols for one futures scan execution."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from apex.application.futures_screening import (
    screen_futures_universe,
    ticker_prefilter_symbols,
)
from apex.application.futures_universe import filter_futures_universe
from apex.application.symbols import load_symbol_file
from apex.data.providers.base import (
    FuturesMarketScreenerProvider,
    FuturesUniverseProvider,
    MarketDataProvider,
)
from apex.domain.futures_screening import (
    FuturesDiscoveryLane,
    FuturesScreenerConfig,
    FuturesScreeningResult,
)
from apex.domain.models import Candle


@dataclass(frozen=True, slots=True)
class FuturesScanSelection:
    """Resolved symbols and optional dynamic-screening diagnostics."""

    symbols: tuple[str, ...]
    screening: FuturesScreeningResult | None

    def __post_init__(self) -> None:
        if not self.symbols:
            raise ValueError("futures scan selection cannot be empty")

    @property
    def used_static_override(self) -> bool:
        """Return whether screening was bypassed by a symbol file."""

        return self.screening is None


def select_futures_scan_symbols(
    universe_provider: FuturesUniverseProvider,
    screener_provider: FuturesMarketScreenerProvider,
    candle_provider: MarketDataProvider | None = None,
    *,
    config: FuturesScreenerConfig,
    symbols_file: Path | None = None,
    quote_asset: str = "USDT",
    blacklist: tuple[str, ...] = (),
    allowlist: tuple[str, ...] | None = None,
) -> FuturesScanSelection:
    """Resolve a static override or run two-stage live screening."""

    if symbols_file is not None:
        return FuturesScanSelection(
            symbols=load_symbol_file(symbols_file),
            screening=None,
        )

    contracts = filter_futures_universe(
        universe_provider.fetch_futures_contracts(),
        quote_asset=quote_asset,
        blacklist=blacklist,
        allowlist=allowlist,
    )
    if not contracts:
        raise ValueError("no eligible futures contracts were discovered")

    tickers = screener_provider.fetch_futures_tickers()
    if candle_provider is None:
        screening = screen_futures_universe(
            contracts,
            tickers,
            config,
        )
        symbols = tuple(candidate.contract.symbol for candidate in screening.candidates)
        if not symbols:
            raise ValueError("lightweight futures screening produced no eligible symbols")
        return FuturesScanSelection(
            symbols=symbols,
            screening=screening,
        )

    prefilter = ticker_prefilter_symbols(
        contracts,
        tickers,
        config,
    )
    candle_sets: dict[str, Sequence[Candle]] = {}
    failures: dict[str, str] = {}
    market_symbols = {
        _normalize_symbol(contract.exchange_symbol): contract.symbol for contract in contracts
    }

    for exchange_symbol in prefilter:
        try:
            candle_sets[exchange_symbol] = tuple(
                candle_provider.fetch_candles(
                    market_symbols[exchange_symbol],
                    config.candle_timeframe,
                    config.candle_limit + 1,
                )
            )
        except Exception as exc:
            failures[exchange_symbol] = (
                f"Limited candle request failed: {type(exc).__name__}: {exc}"
            )

    screening = screen_futures_universe(
        contracts,
        tickers,
        candle_sets,
        config,
        candle_failures=failures,
    )
    symbols = tuple(candidate.contract.symbol for candidate in screening.candidates)
    if not symbols:
        raise ValueError("lightweight futures screening produced no eligible symbols")

    return FuturesScanSelection(
        symbols=symbols,
        screening=screening,
    )


def serialize_futures_screening(
    result: FuturesScreeningResult,
) -> dict[str, object]:
    """Serialize screening features, scores, and exclusions."""

    return {
        "total_contracts": result.total_contracts,
        "total_tickers": result.total_tickers,
        "hard_eligible_count": result.hard_eligible_count,
        "candle_screened_count": result.candle_screened_count,
        "shortlisted_count": result.shortlisted_count,
        "lane_coverage": {
            lane.value: sum(
                any(signal.lane is lane for signal in candidate.discovery_lanes)
                for candidate in result.candidates
            )
            for lane in FuturesDiscoveryLane
        },
        "candidates": [
            {
                "rank": candidate.rank,
                "symbol": candidate.contract.symbol,
                "exchange_symbol": candidate.contract.exchange_symbol,
                "opportunity_score": candidate.opportunity.total,
                "discovery_lanes": [
                    {
                        "lane": signal.lane.value,
                        "score": signal.score,
                        "reason": signal.reason,
                    }
                    for signal in candidate.discovery_lanes
                ],
                "opportunity_components": {
                    "liquidity": candidate.opportunity.liquidity,
                    "movement": candidate.opportunity.movement,
                    "acceleration": candidate.opportunity.acceleration,
                    "relative_volume": candidate.opportunity.relative_volume,
                    "volatility_usability": candidate.opportunity.volatility_usability,
                    "entry_freshness": candidate.opportunity.entry_freshness,
                    "structure_proximity": candidate.opportunity.structure_proximity,
                    "directional_clarity": candidate.opportunity.directional_clarity,
                    "spread_quality": candidate.opportunity.spread_quality,
                    "noise_quality": candidate.opportunity.noise_quality,
                },
                "features": {
                    "return_5m_pct": candidate.features.return_5m_pct,
                    "return_15m_pct": candidate.features.return_15m_pct,
                    "return_30m_pct": candidate.features.return_30m_pct,
                    "return_1h_pct": candidate.features.return_1h_pct,
                    "relative_volume": candidate.features.relative_volume,
                    "volume_acceleration": candidate.features.volume_acceleration,
                    "atr_percentage": candidate.features.atr_percentage,
                    "range_expansion": candidate.features.range_expansion,
                    "trend_slope_percentage": candidate.features.trend_slope_percentage,
                    "breakout_proximity": candidate.features.breakout_proximity,
                    "ema_distance_atr": candidate.features.ema_distance_atr,
                    "wick_intensity": candidate.features.wick_intensity,
                    "directional_persistence": candidate.features.directional_persistence,
                    "current_participation": candidate.features.current_participation,
                    "benchmark_relative_return_1h_pct": (
                        candidate.features.benchmark_relative_return_1h_pct
                    ),
                },
                "reasons": list(candidate.opportunity.reasons),
                "cautions": list(candidate.opportunity.cautions),
                "quote_volume_24h": candidate.ticker.quote_volume_24h,
                "price_change_percentage_24h": (candidate.ticker.price_change_percentage_24h),
                "spread_percentage": candidate.ticker.spread_percentage,
            }
            for candidate in result.candidates
        ],
        "exclusions": [
            {
                "exchange_symbol": exclusion.exchange_symbol,
                "reason": exclusion.reason.value,
                "detail": exclusion.detail,
            }
            for exclusion in result.exclusions
        ],
    }


def _normalize_symbol(value: str) -> str:
    normalized = value.strip().upper().replace("/", "").replace("-", "")
    if not normalized:
        raise ValueError("symbol cannot be empty")
    return normalized
