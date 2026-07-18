"""Typed contracts for lightweight futures-market screening."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.domain.futures_market import FuturesContractMetadata


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty")


def _require_percentage(field_name: str, value: float) -> None:
    if not 0.0 <= value <= 100.0:
        raise ValueError(f"{field_name} must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class FuturesTickerSnapshot:
    """One normalized market-wide futures ticker record."""

    symbol: str
    exchange_symbol: str
    last_price: float
    bid_price: float
    ask_price: float
    quote_volume_24h: float
    price_change_percentage_24h: float
    captured_at: datetime
    source: str
    high_price_24h: float | None = None
    low_price_24h: float | None = None
    trade_count_24h: int | None = None

    def __post_init__(self) -> None:
        for field_name, value in {
            "symbol": self.symbol,
            "exchange_symbol": self.exchange_symbol,
            "source": self.source,
        }.items():
            _require_text(field_name, value)

        if self.last_price <= 0:
            raise ValueError("last_price must be positive")
        if self.bid_price <= 0:
            raise ValueError("bid_price must be positive")
        if self.ask_price <= 0:
            raise ValueError("ask_price must be positive")
        if self.bid_price > self.ask_price:
            raise ValueError("bid_price cannot exceed ask_price")
        if self.quote_volume_24h < 0:
            raise ValueError("quote_volume_24h cannot be negative")
        if self.high_price_24h is not None and self.high_price_24h <= 0:
            raise ValueError("high_price_24h must be positive when provided")
        if self.low_price_24h is not None and self.low_price_24h <= 0:
            raise ValueError("low_price_24h must be positive when provided")
        if (
            self.high_price_24h is not None
            and self.low_price_24h is not None
            and self.low_price_24h > self.high_price_24h
        ):
            raise ValueError("low_price_24h cannot exceed high_price_24h")
        if self.trade_count_24h is not None and self.trade_count_24h < 0:
            raise ValueError("trade_count_24h cannot be negative")

    @property
    def spread(self) -> float:
        """Return the absolute best-bid/best-ask spread."""

        return self.ask_price - self.bid_price

    @property
    def spread_percentage(self) -> float:
        """Return spread as a percentage of the bid/ask midpoint."""

        midpoint = (self.bid_price + self.ask_price) / 2
        return self.spread / midpoint * 100

    @property
    def absolute_movement_percentage(self) -> float:
        """Return the absolute 24-hour price change percentage."""

        return abs(self.price_change_percentage_24h)

    @property
    def range_percentage(self) -> float | None:
        """Return the 24-hour high/low range as a percentage of the low."""

        if self.high_price_24h is None or self.low_price_24h is None:
            return None
        return (self.high_price_24h - self.low_price_24h) / self.low_price_24h * 100


@dataclass(frozen=True, slots=True)
class FuturesOpportunityWeights:
    """Normalized component weights for the opportunity score."""

    liquidity: float = 0.09
    movement: float = 0.10
    acceleration: float = 0.11
    relative_volume: float = 0.13
    volatility_usability: float = 0.10
    entry_freshness: float = 0.14
    structure_proximity: float = 0.12
    directional_clarity: float = 0.08
    spread_quality: float = 0.05
    noise_quality: float = 0.08

    def __post_init__(self) -> None:
        values = self.as_dict().values()
        if any(value < 0 for value in values):
            raise ValueError("opportunity weights cannot be negative")
        if abs(sum(values) - 1.0) > 1e-9:
            raise ValueError("opportunity weights must sum to 1.0")

    def as_dict(self) -> dict[str, float]:
        """Return component weights keyed by score component."""

        return {
            "liquidity": self.liquidity,
            "movement": self.movement,
            "acceleration": self.acceleration,
            "relative_volume": self.relative_volume,
            "volatility_usability": self.volatility_usability,
            "entry_freshness": self.entry_freshness,
            "structure_proximity": self.structure_proximity,
            "directional_clarity": self.directional_clarity,
            "spread_quality": self.spread_quality,
            "noise_quality": self.noise_quality,
        }


@dataclass(frozen=True, slots=True)
class FuturesScreenerConfig:
    """Config-driven hard eligibility and recent-candle scoring."""

    minimum_quote_volume_24h: float = 0.0
    maximum_spread_percentage: float = 100.0
    minimum_absolute_movement_percentage: float = 0.0
    shortlist_size: int = 30
    ticker_prefilter_size: int = 90
    candle_timeframe: str = "5m"
    candle_limit: int = 49
    minimum_candle_count: int = 25
    target_quote_volume_24h: float = 100_000_000.0
    target_movement_percentage: float = 8.0
    target_relative_volume: float = 2.0
    target_atr_percentage: float = 2.0
    maximum_usable_atr_percentage: float = 6.0
    maximum_extension_atr: float = 3.0
    weights: FuturesOpportunityWeights = FuturesOpportunityWeights()

    def __post_init__(self) -> None:
        if self.minimum_quote_volume_24h < 0:
            raise ValueError("minimum_quote_volume_24h cannot be negative")
        if self.maximum_spread_percentage < 0:
            raise ValueError("maximum_spread_percentage cannot be negative")
        if self.minimum_absolute_movement_percentage < 0:
            raise ValueError("minimum_absolute_movement_percentage cannot be negative")
        if self.shortlist_size <= 0:
            raise ValueError("shortlist_size must be positive")
        if self.ticker_prefilter_size < self.shortlist_size:
            raise ValueError("ticker_prefilter_size cannot be below shortlist_size")
        _require_text("candle_timeframe", self.candle_timeframe)
        if self.candle_limit < 13:
            raise ValueError("candle_limit must be at least 13")
        if not 13 <= self.minimum_candle_count <= self.candle_limit:
            raise ValueError("minimum_candle_count must be between 13 and candle_limit")
        positive_values = {
            "target_quote_volume_24h": self.target_quote_volume_24h,
            "target_movement_percentage": self.target_movement_percentage,
            "target_relative_volume": self.target_relative_volume,
            "target_atr_percentage": self.target_atr_percentage,
            "maximum_usable_atr_percentage": (self.maximum_usable_atr_percentage),
            "maximum_extension_atr": self.maximum_extension_atr,
        }
        for field_name, value in positive_values.items():
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")
        if self.maximum_usable_atr_percentage <= self.target_atr_percentage:
            raise ValueError("maximum_usable_atr_percentage must exceed target_atr_percentage")


@dataclass(frozen=True, slots=True)
class FuturesOpportunityFeatures:
    """Cheap recent-candle features derived from one 5m series."""

    return_5m_pct: float
    return_15m_pct: float
    return_30m_pct: float
    return_1h_pct: float
    relative_volume: float
    volume_acceleration: float
    atr_percentage: float
    range_expansion: float
    trend_slope_percentage: float
    breakout_proximity: float
    ema_distance_atr: float
    wick_intensity: float
    directional_persistence: float
    current_participation: float
    benchmark_relative_return_1h_pct: float | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "breakout_proximity",
            "wick_intensity",
            "directional_persistence",
        ):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1")
        for field_name in (
            "relative_volume",
            "volume_acceleration",
            "atr_percentage",
            "range_expansion",
            "ema_distance_atr",
            "current_participation",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")


@dataclass(frozen=True, slots=True)
class FuturesOpportunityScore:
    """Transparent 0-100 opportunity score and diagnostics."""

    total: float
    liquidity: float
    movement: float
    acceleration: float
    relative_volume: float
    volatility_usability: float
    entry_freshness: float
    structure_proximity: float
    directional_clarity: float
    spread_quality: float
    noise_quality: float
    reasons: tuple[str, ...]
    cautions: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "total",
            "liquidity",
            "movement",
            "acceleration",
            "relative_volume",
            "volatility_usability",
            "entry_freshness",
            "structure_proximity",
            "directional_clarity",
            "spread_quality",
            "noise_quality",
        ):
            _require_percentage(field_name, getattr(self, field_name))


class FuturesScreeningExclusionReason(StrEnum):
    """Why a contract did not enter the detailed-analysis shortlist."""

    OUTSIDE_UNIVERSE = "outside_universe"
    MISSING_TICKER = "missing_ticker"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"
    SPREAD_TOO_WIDE = "spread_too_wide"
    INSUFFICIENT_MOVEMENT = "insufficient_movement"
    CANDLE_FETCH_FAILED = "candle_fetch_failed"
    INSUFFICIENT_CANDLE_HISTORY = "insufficient_candle_history"
    INVALID_CANDLE_DATA = "invalid_candle_data"
    BELOW_SHORTLIST = "below_shortlist"


class FuturesDiscoveryLane(StrEnum):
    """Research-derived shortlist lanes used before full trade approval."""

    TREND_CONTINUATION = "trend_continuation"
    COMPRESSION_EXPANSION = "compression_expansion"
    FRESH_BREAK = "fresh_break"
    FAST_MOVER = "fast_mover"
    RANGE_LIQUIDITY_REJECTION = "range_liquidity_rejection"
    RELATIVE_STRENGTH_WEAKNESS = "relative_strength_weakness"
    DEVELOPING = "developing"


@dataclass(frozen=True, slots=True)
class FuturesDiscoveryLaneSignal:
    """One transparent reason a symbol entered the expensive-analysis shortlist."""

    lane: FuturesDiscoveryLane
    score: float
    reason: str

    def __post_init__(self) -> None:
        _require_percentage("discovery lane score", self.score)
        _require_text("discovery lane reason", self.reason)


@dataclass(frozen=True, slots=True)
class FuturesScreeningExclusion:
    """One explicit lightweight-screening exclusion."""

    exchange_symbol: str
    reason: FuturesScreeningExclusionReason
    detail: str

    def __post_init__(self) -> None:
        _require_text("exchange_symbol", self.exchange_symbol)
        _require_text("detail", self.detail)


@dataclass(frozen=True, slots=True)
class FuturesScreeningCandidate:
    """One scored contract selected for detailed analysis."""

    rank: int
    contract: FuturesContractMetadata
    ticker: FuturesTickerSnapshot
    features: FuturesOpportunityFeatures
    opportunity: FuturesOpportunityScore
    discovery_lanes: tuple[FuturesDiscoveryLaneSignal, ...] = ()

    def __post_init__(self) -> None:
        if self.rank <= 0:
            raise ValueError("rank must be positive")


@dataclass(frozen=True, slots=True)
class FuturesScreeningResult:
    """Complete typed result of one lightweight screening pass."""

    total_contracts: int
    total_tickers: int
    hard_eligible_count: int
    candle_screened_count: int
    candidates: tuple[FuturesScreeningCandidate, ...]
    exclusions: tuple[FuturesScreeningExclusion, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "total_contracts",
            "total_tickers",
            "hard_eligible_count",
            "candle_screened_count",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")

    @property
    def shortlisted_count(self) -> int:
        """Return the number of ranked candidates."""

        return len(self.candidates)
