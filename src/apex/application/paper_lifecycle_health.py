"""Deterministic forward-paper lifecycle health and viability gates."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from apex.application.paper_lifecycle_analytics import PaperLifecycleAnalytics

__all__ = [
    "PaperLifecycleHealthPolicy",
    "PaperLifecycleHealthReason",
    "PaperLifecycleHealthReport",
    "PaperLifecycleHealthStatus",
    "evaluate_paper_lifecycle_health",
    "paper_lifecycle_health_payload",
]


class PaperLifecycleHealthStatus(StrEnum):
    """Stable forward-paper viability outcomes."""

    INSUFFICIENT_SAMPLE = "insufficient_sample"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class PaperLifecycleHealthReason(StrEnum):
    """Machine-readable lifecycle health findings."""

    INSUFFICIENT_TERMINAL_SAMPLE = "insufficient_terminal_sample"
    PROVIDER_FAILURE_RATE_EXCEEDED = "provider_failure_rate_exceeded"
    MISSING_CANDLE_RATE_EXCEEDED = "missing_candle_rate_exceeded"
    PERSISTENCE_FAILURE_RATE_EXCEEDED = "persistence_failure_rate_exceeded"
    INVALIDATION_RATE_EXCEEDED = "invalidation_rate_exceeded"
    UNFILLED_TERMINAL_RATE_EXCEEDED = "unfilled_terminal_rate_exceeded"
    AVERAGE_R_BELOW_MINIMUM = "average_r_below_minimum"
    NET_PNL_BELOW_MINIMUM = "net_pnl_below_minimum"
    REALIZED_PERFORMANCE_UNAVAILABLE = "realized_performance_unavailable"


@dataclass(frozen=True, slots=True)
class PaperLifecycleHealthPolicy:
    """Configuration for deterministic forward-paper viability evaluation."""

    minimum_terminal_trades: int = 20
    maximum_provider_failure_rate: float = 0.10
    maximum_missing_candle_rate: float = 0.10
    maximum_persistence_failure_rate: float = 0.02
    maximum_invalidation_rate: float = 0.25
    maximum_unfilled_terminal_rate: float = 0.40
    minimum_average_realized_r: float = 0.0
    minimum_realized_net_pnl: float = 0.0
    require_realized_performance: bool = True

    def __post_init__(self) -> None:
        if self.minimum_terminal_trades < 1:
            raise ValueError("minimum terminal trades must be positive")
        for name in (
            "maximum_provider_failure_rate",
            "maximum_missing_candle_rate",
            "maximum_persistence_failure_rate",
            "maximum_invalidation_rate",
            "maximum_unfilled_terminal_rate",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name.replace('_', ' ')} must be between zero and one")
        for name in ("minimum_average_realized_r", "minimum_realized_net_pnl"):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")


@dataclass(frozen=True, slots=True)
class PaperLifecycleHealthReport:
    """Auditable forward-paper lifecycle health decision."""

    status: PaperLifecycleHealthStatus
    reasons: tuple[PaperLifecycleHealthReason, ...]
    terminal_trade_count: int
    entered_trade_count: int
    requested_symbol_count: int
    provider_failure_count: int
    provider_failure_rate: float
    loaded_trade_count: int
    missing_candle_trade_count: int
    missing_candle_rate: float
    intake_accepted_count: int
    persistence_failure_count: int
    persistence_failure_rate: float
    invalidation_count: int
    invalidation_rate: float
    unfilled_terminal_count: int
    unfilled_terminal_rate: float
    realized_net_pnl: float | None
    average_realized_r_multiple: float | None
    sample_shortfall: int

    @property
    def ready_for_forward_viability_review(self) -> bool:
        """Return whether the health gate has enough evidence and has not failed."""

        return self.status in {
            PaperLifecycleHealthStatus.HEALTHY,
            PaperLifecycleHealthStatus.DEGRADED,
        }


_HARD_FAILURE_REASONS = frozenset(
    {
        PaperLifecycleHealthReason.PROVIDER_FAILURE_RATE_EXCEEDED,
        PaperLifecycleHealthReason.MISSING_CANDLE_RATE_EXCEEDED,
        PaperLifecycleHealthReason.PERSISTENCE_FAILURE_RATE_EXCEEDED,
    }
)


_DEGRADED_REASONS = frozenset(
    {
        PaperLifecycleHealthReason.INVALIDATION_RATE_EXCEEDED,
        PaperLifecycleHealthReason.UNFILLED_TERMINAL_RATE_EXCEEDED,
        PaperLifecycleHealthReason.AVERAGE_R_BELOW_MINIMUM,
        PaperLifecycleHealthReason.NET_PNL_BELOW_MINIMUM,
        PaperLifecycleHealthReason.REALIZED_PERFORMANCE_UNAVAILABLE,
    }
)


def evaluate_paper_lifecycle_health(
    analytics: PaperLifecycleAnalytics,
    *,
    policy: PaperLifecycleHealthPolicy | None = None,
) -> PaperLifecycleHealthReport:
    """Evaluate forward-paper lifecycle reliability and viability deterministically."""

    active_policy = policy or PaperLifecycleHealthPolicy()
    terminal_count = sum(
        analytics.state_counts.get(state, 0)
        for state in ("stopped", "target_hit", "expired", "cancelled", "invalidated")
    )
    provider_failure_rate = _safe_rate(
        analytics.provider_failure_count,
        analytics.requested_symbols,
    )
    missing_candle_rate = _safe_rate(
        analytics.missing_candle_trades,
        analytics.loaded_trades,
    )
    persistence_failure_rate = _safe_rate(
        analytics.persistence_failures,
        analytics.intake_accepted + analytics.persistence_failures,
    )
    invalidation_rate = _safe_rate(analytics.invalidations, terminal_count)
    unfilled_terminal_rate = _safe_rate(analytics.unfilled_terminal_trades, terminal_count)

    reasons: list[PaperLifecycleHealthReason] = []
    if provider_failure_rate > active_policy.maximum_provider_failure_rate:
        reasons.append(PaperLifecycleHealthReason.PROVIDER_FAILURE_RATE_EXCEEDED)
    if missing_candle_rate > active_policy.maximum_missing_candle_rate:
        reasons.append(PaperLifecycleHealthReason.MISSING_CANDLE_RATE_EXCEEDED)
    if persistence_failure_rate > active_policy.maximum_persistence_failure_rate:
        reasons.append(PaperLifecycleHealthReason.PERSISTENCE_FAILURE_RATE_EXCEEDED)
    if invalidation_rate > active_policy.maximum_invalidation_rate:
        reasons.append(PaperLifecycleHealthReason.INVALIDATION_RATE_EXCEEDED)
    if unfilled_terminal_rate > active_policy.maximum_unfilled_terminal_rate:
        reasons.append(PaperLifecycleHealthReason.UNFILLED_TERMINAL_RATE_EXCEEDED)

    realized_available = (
        analytics.realized_net_pnl is not None
        and analytics.average_realized_r_multiple is not None
    )
    if active_policy.require_realized_performance and not realized_available:
        reasons.append(PaperLifecycleHealthReason.REALIZED_PERFORMANCE_UNAVAILABLE)
    else:
        if (
            analytics.average_realized_r_multiple is not None
            and analytics.average_realized_r_multiple
            < active_policy.minimum_average_realized_r
        ):
            reasons.append(PaperLifecycleHealthReason.AVERAGE_R_BELOW_MINIMUM)
        if (
            analytics.realized_net_pnl is not None
            and analytics.realized_net_pnl < active_policy.minimum_realized_net_pnl
        ):
            reasons.append(PaperLifecycleHealthReason.NET_PNL_BELOW_MINIMUM)

    sample_shortfall = max(active_policy.minimum_terminal_trades - terminal_count, 0)
    if sample_shortfall:
        reasons.append(PaperLifecycleHealthReason.INSUFFICIENT_TERMINAL_SAMPLE)

    reason_set = frozenset(reasons)
    if reason_set & _HARD_FAILURE_REASONS:
        status = PaperLifecycleHealthStatus.FAILED
    elif sample_shortfall:
        status = PaperLifecycleHealthStatus.INSUFFICIENT_SAMPLE
    elif reason_set & _DEGRADED_REASONS:
        status = PaperLifecycleHealthStatus.DEGRADED
    else:
        status = PaperLifecycleHealthStatus.HEALTHY

    return PaperLifecycleHealthReport(
        status=status,
        reasons=tuple(sorted(reasons, key=str)),
        terminal_trade_count=terminal_count,
        entered_trade_count=analytics.entered_trades,
        requested_symbol_count=analytics.requested_symbols,
        provider_failure_count=analytics.provider_failure_count,
        provider_failure_rate=provider_failure_rate,
        loaded_trade_count=analytics.loaded_trades,
        missing_candle_trade_count=analytics.missing_candle_trades,
        missing_candle_rate=missing_candle_rate,
        intake_accepted_count=analytics.intake_accepted,
        persistence_failure_count=analytics.persistence_failures,
        persistence_failure_rate=persistence_failure_rate,
        invalidation_count=analytics.invalidations,
        invalidation_rate=invalidation_rate,
        unfilled_terminal_count=analytics.unfilled_terminal_trades,
        unfilled_terminal_rate=unfilled_terminal_rate,
        realized_net_pnl=analytics.realized_net_pnl,
        average_realized_r_multiple=analytics.average_realized_r_multiple,
        sample_shortfall=sample_shortfall,
    )


def paper_lifecycle_health_payload(report: PaperLifecycleHealthReport) -> dict[str, Any]:
    """Return one stable JSON-ready lifecycle health payload."""

    return asdict(report)


def _safe_rate(numerator: int, denominator: int) -> float:
    if numerator < 0 or denominator < 0:
        raise ValueError("health rate inputs cannot be negative")
    if denominator == 0:
        return 0.0
    return numerator / denominator
