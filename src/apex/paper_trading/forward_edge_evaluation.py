"""Deterministic forward-paper evidence aggregation and promotion."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import fmean

from apex.backtesting import (
    EvidenceQuality,
    HistoricalEdgeValidationResult,
    HistoricalEdgeValidationStatus,
)
from apex.paper_trading.contracts import PaperTrade, PaperTradeState
from apex.paper_trading.forward_edge_contracts import (
    ForwardPaperEdgeProfile,
    ForwardPaperValidationPolicy,
    ForwardPaperValidationReason,
    ForwardPaperValidationResult,
    ForwardPaperValidationStatus,
)

_CLOSED_OUTCOME_STATES = {PaperTradeState.STOPPED, PaperTradeState.TARGET_HIT}


def build_forward_paper_edge_profile(
    trades: Sequence[PaperTrade],
    *,
    dimensions: Mapping[str, str],
) -> ForwardPaperEdgeProfile:
    """Build one profile from matching entered and terminal paper trades."""

    completed = tuple(
        sorted(
            (
                trade
                for trade in trades
                if trade.state in _CLOSED_OUTCOME_STATES
                and trade.entry_time is not None
                and trade.exit_time is not None
                and _matches_dimensions(trade, dimensions)
            ),
            key=lambda trade: (trade.exit_time, trade.trade_id),
        )
    )
    if not completed:
        raise ValueError("forward-paper aggregation requires at least one completed trade")

    r_values = tuple(trade.realized_r_multiple for trade in completed)
    wins = tuple(value for value in r_values if value > 0.0)
    losses = tuple(value for value in r_values if value < 0.0)
    gross_loss = abs(sum(losses))
    profit_factor = sum(wins) / gross_loss if gross_loss > 0.0 else None
    return ForwardPaperEdgeProfile(
        dimensions=dimensions,
        sample_size=len(completed),
        win_rate=len(wins) / len(completed),
        expectancy=fmean(r_values),
        profit_factor=profit_factor,
        maximum_drawdown_r=_maximum_drawdown(r_values),
    )


def evaluate_forward_paper_edge(
    historical_validation: HistoricalEdgeValidationResult,
    trades: Sequence[PaperTrade],
    *,
    dimensions: Mapping[str, str] | None = None,
    policy: ForwardPaperValidationPolicy | None = None,
) -> ForwardPaperValidationResult:
    """Evaluate forward-paper evidence after passed out-of-sample validation."""

    resolved_policy = policy or ForwardPaperValidationPolicy()
    resolved_dimensions = dict(dimensions or historical_validation.dimensions)
    reasons: list[ForwardPaperValidationReason] = []

    historical_ready = (
        historical_validation.status is HistoricalEdgeValidationStatus.PASSED_VALIDATION
        and historical_validation.promoted_evidence_quality
        is EvidenceQuality.VALIDATED_OUT_OF_SAMPLE
        and historical_validation.evidence_stable
    )
    if not historical_ready:
        reasons.append(ForwardPaperValidationReason.HISTORICAL_OUT_OF_SAMPLE_REQUIRED)
    if resolved_dimensions != dict(historical_validation.dimensions):
        reasons.append(ForwardPaperValidationReason.SEGMENT_DIMENSIONS_MISMATCH)

    try:
        profile = build_forward_paper_edge_profile(trades, dimensions=resolved_dimensions)
    except ValueError:
        profile = None

    if profile is None or profile.sample_size < resolved_policy.minimum_closed_trades:
        reasons.append(ForwardPaperValidationReason.FORWARD_SAMPLE_INSUFFICIENT)
    if profile is not None:
        if profile.expectancy <= 0.0:
            reasons.append(ForwardPaperValidationReason.FORWARD_EXPECTANCY_NOT_POSITIVE)
        if not _profit_factor_exceeds(profile.profit_factor, resolved_policy.minimum_profit_factor):
            reasons.append(ForwardPaperValidationReason.FORWARD_PROFIT_FACTOR_INADEQUATE)

    test_expectancy = historical_validation.test_expectancy
    degradation = _expectancy_degradation(test_expectancy, profile)
    if (
        degradation is not None
        and degradation > resolved_policy.maximum_expectancy_degradation_from_test
    ):
        reasons.append(ForwardPaperValidationReason.EXPECTANCY_DEGRADATION_EXCESSIVE)

    consistent_direction = bool(
        test_expectancy is not None
        and test_expectancy > 0.0
        and profile is not None
        and profile.expectancy > 0.0
    )
    if profile is not None and not consistent_direction:
        reasons.append(ForwardPaperValidationReason.EDGE_DIRECTION_INCONSISTENT)

    reasons = list(dict.fromkeys(reasons))
    insufficient = {
        ForwardPaperValidationReason.HISTORICAL_OUT_OF_SAMPLE_REQUIRED,
        ForwardPaperValidationReason.FORWARD_SAMPLE_INSUFFICIENT,
    }
    degradation_only = {ForwardPaperValidationReason.EXPECTANCY_DEGRADATION_EXCESSIVE}
    if any(reason in insufficient for reason in reasons):
        status = ForwardPaperValidationStatus.INSUFFICIENT_SAMPLE
    elif any(reason not in degradation_only for reason in reasons):
        status = ForwardPaperValidationStatus.FAILED_VALIDATION
    elif reasons:
        status = ForwardPaperValidationStatus.DEGRADED_VALIDATION
    else:
        status = ForwardPaperValidationStatus.PASSED_VALIDATION

    passed = status is ForwardPaperValidationStatus.PASSED_VALIDATION
    return ForwardPaperValidationResult(
        dimensions=resolved_dimensions,
        status=status,
        historical_validation=historical_validation,
        forward_profile=profile,
        expectancy_degradation_from_test=degradation,
        consistent_edge_direction=consistent_direction,
        evidence_stable=passed,
        promoted_evidence_quality=(
            EvidenceQuality.VALIDATED_FORWARD_PAPER if passed else None
        ),
        rejection_reasons=tuple(reasons),
        warnings=(ForwardPaperValidationReason.PRODUCTION_ELIGIBILITY_NOT_INCLUDED,)
        if passed
        else (),
    )


def _matches_dimensions(trade: PaperTrade, dimensions: Mapping[str, str]) -> bool:
    values = {
        "strategy": trade.signal.strategy.value,
        "direction": trade.signal.direction.value,
        "symbol": trade.signal.symbol,
        "risk_mode": str(trade.analysis_payload.get("active_risk_mode", "STANDARD")),
        "market_type": str(trade.analysis_payload.get("market_type", "futures")),
        "market_regime": str(trade.analysis_payload.get("market_regime", "unknown")),
        "entry_state": str(trade.analysis_payload.get("entry_state", "unknown")),
    }
    return all(
        values.get(name, str(trade.analysis_payload.get(name, "unknown"))) == value
        for name, value in dimensions.items()
    )


def _profit_factor_exceeds(value: float | None, minimum: float) -> bool:
    return value is None or value > minimum


def _expectancy_degradation(
    test_expectancy: float | None,
    profile: ForwardPaperEdgeProfile | None,
) -> float | None:
    if test_expectancy is None or test_expectancy <= 0.0 or profile is None:
        return None
    return (test_expectancy - profile.expectancy) / test_expectancy


def _maximum_drawdown(r_values: Sequence[float]) -> float:
    equity = peak = maximum = 0.0
    for value in r_values:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum
