"""Optional deterministic Phase 11 market-intelligence calculations."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from itertools import pairwise

from apex.domain.models import Candle
from apex.intelligence.contracts import (
    FundingRateSnapshot,
    MarketWideRiskSummary,
    OpenInterestSnapshot,
    SymbolCorrelation,
)


def calculate_symbol_correlation(
    base_symbol: str,
    compared_symbol: str,
    base_candles: Sequence[Candle],
    compared_candles: Sequence[Candle],
) -> SymbolCorrelation:
    """Calculate close-return correlation without future data."""

    base_returns = _returns(base_candles)
    compared_returns = _returns(compared_candles)
    sample_size = min(len(base_returns), len(compared_returns))
    if sample_size < 2:
        raise ValueError("at least two aligned returns are required")
    base = base_returns[-sample_size:]
    compared = compared_returns[-sample_size:]
    return SymbolCorrelation(
        base_symbol=base_symbol,
        compared_symbol=compared_symbol,
        correlation=_pearson(base, compared),
        sample_size=sample_size,
    )


def summarize_market_risk(
    *,
    funding: Sequence[FundingRateSnapshot] = (),
    open_interest: Sequence[OpenInterestSnapshot] = (),
    correlations: Sequence[SymbolCorrelation] = (),
) -> MarketWideRiskSummary:
    """Create metadata/warnings only; this does not approve or reject trades."""

    warnings: list[str] = []
    risk_score = 0.0
    if any(abs(item.funding_rate) >= 0.001 for item in funding):
        risk_score += 0.3
        warnings.append("elevated funding pressure")
    if any(item.open_interest > 0.0 for item in open_interest):
        risk_score += 0.1
    if any(abs(item.correlation) >= 0.85 for item in correlations):
        risk_score += 0.3
        warnings.append("high cross-symbol correlation")
    return MarketWideRiskSummary(
        risk_score=min(1.0, risk_score),
        warnings=tuple(dict.fromkeys(warnings)),
        funding=tuple(funding),
        open_interest=tuple(open_interest),
        correlations=tuple(correlations),
    )


def intelligence_metadata(summary: MarketWideRiskSummary) -> dict[str, object]:
    """Return analysis metadata suitable for reports, not decision control."""

    return {
        "risk_score": summary.risk_score,
        "warnings": list(summary.warnings),
        "funding_count": len(summary.funding),
        "open_interest_count": len(summary.open_interest),
        "correlation_count": len(summary.correlations),
    }


def disabled_intelligence_metadata() -> dict[str, object]:
    return {"enabled": False, "warnings": []}


def correlation_matrix(
    candles_by_symbol: Mapping[str, Sequence[Candle]],
) -> tuple[SymbolCorrelation, ...]:
    symbols = tuple(candles_by_symbol)
    correlations: list[SymbolCorrelation] = []
    for index, symbol in enumerate(symbols):
        for other in symbols[index + 1 :]:
            correlations.append(
                calculate_symbol_correlation(
                    symbol,
                    other,
                    candles_by_symbol[symbol],
                    candles_by_symbol[other],
                )
            )
    return tuple(correlations)


def _returns(candles: Sequence[Candle]) -> tuple[float, ...]:
    closes = tuple(candle.close for candle in candles)
    return tuple((current - previous) / previous for previous, current in pairwise(closes))


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_denominator = math.sqrt(sum((value - left_mean) ** 2 for value in left))
    right_denominator = math.sqrt(sum((value - right_mean) ** 2 for value in right))
    denominator = left_denominator * right_denominator
    if denominator == 0.0:
        return 0.0
    return numerator / denominator
