"""Stage 3 strategy-family identifiers."""

from enum import StrEnum


class CanonicalStrategyFamily(StrEnum):
    TREND_PULLBACK = "trend_pullback"
    BREAK_CONTINUATION = "break_continuation"
    BREAK_RETEST = "break_retest"
    COMPRESSION_EXPANSION = "compression_expansion"
    RANGE_REJECTION = "range_rejection"
    FAILED_BREAK_RECLAIM = "failed_break_reclaim"
    LIQUIDITY_SWEEP_REVERSAL = "liquidity_sweep_reversal"


class StrategyType(StrEnum):
    """Distinct trade-discovery strategy families."""

    MOMENTUM_BREAKOUT = "momentum_breakout"
    BREAKOUT_CONTINUATION = "breakout_continuation"
    BREAKOUT_RETEST = "breakout_retest"
    FIRST_PULLBACK_CONTINUATION = "first_pullback_continuation"
    TREND_PULLBACK = "trend_pullback"
    COMPRESSION_EXPANSION = "compression_expansion"
    RANGE_REVERSAL = "range_reversal"
    FAILED_BREAKOUT_REVERSAL = "failed_breakout_reversal"
    LIQUIDITY_REJECTION_REVERSAL = "liquidity_rejection_reversal"
    VWAP_RECLAIM_REJECTION = "vwap_reclaim_rejection"
    MOMENTUM_SCALP = "momentum_scalp"
    EXHAUSTION_REVERSAL = "exhaustion_reversal"

    @property
    def canonical_family(self) -> CanonicalStrategyFamily:
        return _CANONICAL_FAMILY[self]

    @property
    def canonical_subtype(self) -> str | None:
        family = self.canonical_family.value
        return None if self.value == family else self.value


_CANONICAL_FAMILY: dict[StrategyType, CanonicalStrategyFamily] = {
    StrategyType.MOMENTUM_BREAKOUT: CanonicalStrategyFamily.BREAK_CONTINUATION,
    StrategyType.BREAKOUT_CONTINUATION: CanonicalStrategyFamily.BREAK_CONTINUATION,
    StrategyType.BREAKOUT_RETEST: CanonicalStrategyFamily.BREAK_RETEST,
    StrategyType.FIRST_PULLBACK_CONTINUATION: CanonicalStrategyFamily.TREND_PULLBACK,
    StrategyType.TREND_PULLBACK: CanonicalStrategyFamily.TREND_PULLBACK,
    StrategyType.COMPRESSION_EXPANSION: CanonicalStrategyFamily.COMPRESSION_EXPANSION,
    StrategyType.RANGE_REVERSAL: CanonicalStrategyFamily.RANGE_REJECTION,
    StrategyType.FAILED_BREAKOUT_REVERSAL: CanonicalStrategyFamily.FAILED_BREAK_RECLAIM,
    StrategyType.LIQUIDITY_REJECTION_REVERSAL: CanonicalStrategyFamily.LIQUIDITY_SWEEP_REVERSAL,
    StrategyType.VWAP_RECLAIM_REJECTION: CanonicalStrategyFamily.TREND_PULLBACK,
    StrategyType.MOMENTUM_SCALP: CanonicalStrategyFamily.BREAK_CONTINUATION,
    StrategyType.EXHAUSTION_REVERSAL: CanonicalStrategyFamily.LIQUIDITY_SWEEP_REVERSAL,
}
