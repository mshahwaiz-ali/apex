"""Stage 3 strategy-family identifiers."""

from enum import StrEnum


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
    LIQUIDITY_REVERSAL = "liquidity_reversal"
    VWAP_RECLAIM_REJECTION = "vwap_reclaim_rejection"
    MOMENTUM_SCALP = "momentum_scalp"
    EXHAUSTION_REVERSAL = "exhaustion_reversal"
    MOMENTUM_CONTINUATION = "momentum_continuation"
