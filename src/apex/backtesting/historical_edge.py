"""Setup-specific historical edge aggregation for completed backtest trades."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import fmean, median
from types import MappingProxyType

from apex.backtesting.contracts import SimulatedTrade

DEFAULT_EDGE_SEGMENTS = (
    "market_type",
    "strategy",
    "direction",
    "symbol",
    "market_regime",
    "score_band",
    "entry_state",
    "risk_mode",
)


class EvidenceQuality(StrEnum):
    """Evidence maturity for one setup-specific historical segment."""

    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    PROMISING = "PROMISING"
    VALIDATED_BACKTEST = "VALIDATED_BACKTEST"
    VALIDATED_OUT_OF_SAMPLE = "VALIDATED_OUT_OF_SAMPLE"
    VALIDATED_FORWARD_PAPER = "VALIDATED_FORWARD_PAPER"
    PRODUCTION_ELIGIBLE = "PRODUCTION_ELIGIBLE"
    DEGRADED = "DEGRADED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class HistoricalEdgeProfile:
    """Immutable metrics for one deterministic trade segment."""

    dimensions: Mapping[str, str]
    sample_size: int
    win_rate: float
    loss_rate: float
    breakeven_rate: float
    average_r: float
    median_r: float
    expectancy: float
    profit_factor: float | None
    maximum_drawdown_r: float
    maximum_losing_streak: int
    average_holding_candles: float
    average_execution_cost_r: float
    evidence_quality: EvidenceQuality
    out_of_sample_validated: bool = False
    forward_paper_validated: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.sample_size < 1:
            raise ValueError("historical edge profile requires at least one trade")
        for name in ("win_rate", "loss_rate", "breakeven_rate"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name.replace('_', ' ')} must be in the unit interval")
        for name in (
            "average_r",
            "median_r",
            "expectancy",
            "maximum_drawdown_r",
            "average_holding_candles",
            "average_execution_cost_r",
        ):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        if self.maximum_drawdown_r < 0.0:
            raise ValueError("maximum drawdown cannot be negative")
        if self.maximum_losing_streak < 0:
            raise ValueError("maximum losing streak cannot be negative")
        if self.profit_factor is not None and (
            not math.isfinite(self.profit_factor) or self.profit_factor < 0.0
        ):
            raise ValueError("profit factor must be finite and non-negative")
        if self.evidence_quality in {
            EvidenceQuality.VALIDATED_OUT_OF_SAMPLE,
            EvidenceQuality.VALIDATED_FORWARD_PAPER,
            EvidenceQuality.PRODUCTION_ELIGIBLE,
        }:
            raise ValueError("V1.1 profiles cannot claim external validation")
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))


def aggregate_historical_edges(
    trades: Sequence[SimulatedTrade],
    *,
    segment_by: Sequence[str] = DEFAULT_EDGE_SEGMENTS,
) -> tuple[HistoricalEdgeProfile, ...]:
    """Aggregate completed trades into deterministic setup-specific profiles."""

    dimensions = tuple(segment_by)
    if len(set(dimensions)) != len(dimensions):
        raise ValueError("historical edge segmentation dimensions must be unique")
    if any(not dimension.strip() for dimension in dimensions):
        raise ValueError("historical edge segmentation dimensions cannot be empty")

    grouped: dict[tuple[str, ...], list[SimulatedTrade]] = defaultdict(list)
    for trade in sorted(
        trades,
        key=lambda item: (item.exit_time, item.signal.symbol, item.signal.strategy.value),
    ):
        key = tuple(_dimension_value(trade, dimension) for dimension in dimensions)
        grouped[key].append(trade)

    profiles = [
        _build_profile(
            tuple(grouped[key]),
            dimensions=dict(zip(dimensions, key, strict=True)),
        )
        for key in sorted(grouped)
    ]
    return tuple(profiles)


def build_historical_edge_profile(
    trades: Sequence[SimulatedTrade],
    *,
    dimensions: Mapping[str, str] | None = None,
) -> HistoricalEdgeProfile:
    """Build one profile from a non-empty completed-trade sample."""

    ordered = tuple(
        sorted(
            trades,
            key=lambda item: (item.exit_time, item.signal.symbol, item.signal.strategy.value),
        )
    )
    return _build_profile(ordered, dimensions=dict(dimensions or {}))


def _build_profile(
    trades: tuple[SimulatedTrade, ...],
    *,
    dimensions: Mapping[str, str],
) -> HistoricalEdgeProfile:
    if not trades:
        raise ValueError("historical edge aggregation requires at least one trade")

    r_values = tuple(trade.realized_r_multiple for trade in trades)
    wins = tuple(value for value in r_values if value > 0.0)
    losses = tuple(value for value in r_values if value < 0.0)
    breakeven_count = len(r_values) - len(wins) - len(losses)
    sample_size = len(trades)
    gross_profit_r = sum(wins)
    gross_loss_r = abs(sum(losses))
    profit_factor = gross_profit_r / gross_loss_r if gross_loss_r > 0.0 else None
    expectancy = fmean(r_values)
    evidence_quality = _classify_evidence(
        sample_size=sample_size,
        expectancy=expectancy,
        profit_factor=profit_factor,
    )
    warnings = _evidence_warnings(sample_size, expectancy, profit_factor)

    return HistoricalEdgeProfile(
        dimensions=dimensions,
        sample_size=sample_size,
        win_rate=len(wins) / sample_size,
        loss_rate=len(losses) / sample_size,
        breakeven_rate=breakeven_count / sample_size,
        average_r=expectancy,
        median_r=float(median(r_values)),
        expectancy=expectancy,
        profit_factor=profit_factor,
        maximum_drawdown_r=_maximum_drawdown(r_values),
        maximum_losing_streak=_maximum_losing_streak(r_values),
        average_holding_candles=fmean(trade.holding_candles for trade in trades),
        average_execution_cost_r=fmean(
            trade.fees / trade.signal.risk_amount for trade in trades
        ),
        evidence_quality=evidence_quality,
        warnings=warnings,
    )


def _dimension_value(trade: SimulatedTrade, dimension: str) -> str:
    if dimension == "market_type":
        return str(trade.metadata.get("market_type", "futures"))
    if dimension == "strategy":
        return trade.signal.strategy.value
    if dimension == "direction":
        return trade.signal.direction.value
    if dimension == "symbol":
        return trade.signal.symbol
    if dimension == "score_band":
        explicit = trade.metadata.get("score_band")
        return str(explicit) if explicit is not None else _score_band(trade.signal.confidence_score)
    if dimension == "risk_mode":
        return str(trade.metadata.get("active_risk_mode", "STANDARD"))
    value = trade.metadata.get(dimension, "unknown")
    return str(value)


def _score_band(score: float) -> str:
    lower = int(score // 10) * 10
    upper = min(lower + 9, 100)
    return f"{lower:02d}_{upper:02d}"


def _maximum_drawdown(r_values: Sequence[float]) -> float:
    equity = peak = maximum = 0.0
    for value in r_values:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def _maximum_losing_streak(r_values: Sequence[float]) -> int:
    current = maximum = 0
    for value in r_values:
        current = current + 1 if value < 0.0 else 0
        maximum = max(maximum, current)
    return maximum


def _classify_evidence(
    *,
    sample_size: int,
    expectancy: float,
    profit_factor: float | None,
) -> EvidenceQuality:
    if sample_size < 30:
        return EvidenceQuality.INSUFFICIENT_SAMPLE
    if sample_size < 100:
        return EvidenceQuality.RESEARCH_ONLY

    positive_edge = expectancy > 0.0 and (profit_factor is None or profit_factor > 1.0)
    if sample_size < 250:
        return EvidenceQuality.PROMISING if positive_edge else EvidenceQuality.DEGRADED
    return EvidenceQuality.VALIDATED_BACKTEST if positive_edge else EvidenceQuality.REJECTED


def _evidence_warnings(
    sample_size: int,
    expectancy: float,
    profit_factor: float | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if sample_size < 30:
        warnings.append("sample size is below the minimum research threshold")
    elif sample_size < 250:
        warnings.append("sample size is below the stronger-evidence threshold")
    if expectancy <= 0.0:
        warnings.append("historical expectancy is not positive")
    if profit_factor is not None and profit_factor <= 1.0:
        warnings.append("historical profit factor does not exceed one")
    warnings.append("out-of-sample and forward-paper validation are not included")
    return tuple(warnings)
