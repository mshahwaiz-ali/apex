"""Market-state and strategy contracts defined by the trade methodology."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.application.methodology_contracts import EvidenceFamily


class PrimaryMarketState(StrEnum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    COMPRESSING = "compressing"
    BREAKOUT_ATTEMPT = "breakout_attempt"
    BREAKDOWN_ATTEMPT = "breakdown_attempt"
    POST_BREAKOUT = "post_breakout"
    POST_BREAKDOWN = "post_breakdown"
    PULLBACK_IN_UPTREND = "pullback_in_uptrend"
    RALLY_IN_DOWNTREND = "rally_in_downtrend"
    REVERSAL_ATTEMPT_UP = "reversal_attempt_up"
    REVERSAL_ATTEMPT_DOWN = "reversal_attempt_down"
    EXHAUSTED_UP = "exhausted_up"
    EXHAUSTED_DOWN = "exhausted_down"
    TRANSITIONAL = "transitional"
    CHAOTIC = "chaotic"


class SecondaryMarketCondition(StrEnum):
    VOLATILITY_EXPANSION = "volatility_expansion"
    VOLATILITY_CONTRACTION = "volatility_contraction"
    VOLUME_EXPANSION = "volume_expansion"
    VOLUME_DIVERGENCE = "volume_divergence"
    OPEN_INTEREST_EXPANSION = "open_interest_expansion"
    OPEN_INTEREST_CONTRACTION = "open_interest_contraction"
    OVEREXTENDED = "overextended"
    NEAR_MAJOR_SUPPORT = "near_major_support"
    NEAR_MAJOR_RESISTANCE = "near_major_resistance"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    FAILED_BREAKOUT = "failed_breakout"
    FAILED_BREAKDOWN = "failed_breakdown"
    MILD_HTF_CONFLICT = "mild_htf_conflict"
    STRONG_HTF_CONFLICT = "strong_htf_conflict"
    DIRECT_STRUCTURAL_OPPOSITION = "direct_structural_opposition"


class SetupMaturity(StrEnum):
    PATTERN_DEVELOPING = "pattern_developing"
    TRIGGER_PROVISIONAL = "trigger_provisional"
    CONFIRMATION_PENDING_CLOSE = "confirmation_pending_close"
    SETUP_CONFIRMED = "setup_confirmed"
    RETEST_PENDING = "retest_pending"
    RECLAIM_PENDING = "reclaim_pending"
    ENTRY_AVAILABLE = "entry_available"
    ENTRY_LATE = "entry_late"
    ENTRY_MISSED = "entry_missed"
    PATTERN_FAILED = "pattern_failed"
    INVALIDATED = "invalidated"


class ConfirmationPolicy(StrEnum):
    CLOSE_REQUIRED = "close_required"
    INTRABAR_ALLOWED = "intrabar_allowed"
    LOWER_TIMEFRAME_CONFIRMATION_ALLOWED = "lower_timeframe_confirmation_allowed"
    RETEST_REQUIRED = "retest_required"
    RECLAIM_REQUIRED = "reclaim_required"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class MarketStateClassification:
    primary: PrimaryMarketState
    secondary: tuple[SecondaryMarketCondition, ...]
    evidence_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if not self.evidence_ids:
            raise ValueError("market-state classification requires evidence")
        if len(set(self.secondary)) != len(self.secondary):
            raise ValueError("secondary market conditions must be unique")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("market-state evidence identifiers must be unique")
        if any(not item.strip() for item in self.evidence_ids):
            raise ValueError("market-state evidence identifiers cannot be blank")
        if not self.reason.strip():
            raise ValueError("market-state reason cannot be empty")


@dataclass(frozen=True, slots=True)
class StrategyEligibility:
    strategy_id: str
    strategy_version: str
    compatible_states: tuple[PrimaryMarketState, ...]
    prohibited_states: tuple[PrimaryMarketState, ...]
    mandatory_evidence: tuple[EvidenceFamily, ...]
    optional_evidence: tuple[EvidenceFamily, ...]
    confirmation_policy: ConfirmationPolicy
    entry_models: tuple[str, ...]
    invalidation_method: str
    target_methods: tuple[str, ...]
    expiry_policy: str
    historical_segment_key: str

    def __post_init__(self) -> None:
        for name, value in (
            ("strategy id", self.strategy_id),
            ("strategy version", self.strategy_version),
            ("invalidation method", self.invalidation_method),
            ("expiry policy", self.expiry_policy),
            ("historical segment key", self.historical_segment_key),
        ):
            if not value.strip():
                raise ValueError(f"{name} cannot be empty")
        if not self.compatible_states:
            raise ValueError("strategy requires at least one compatible state")
        if set(self.compatible_states) & set(self.prohibited_states):
            raise ValueError("compatible and prohibited states cannot overlap")
        if not self.mandatory_evidence:
            raise ValueError("strategy requires mandatory evidence")
        if set(self.mandatory_evidence) & set(self.optional_evidence):
            raise ValueError("mandatory and optional evidence cannot overlap")
        if not self.entry_models or any(not item.strip() for item in self.entry_models):
            raise ValueError("strategy requires non-empty entry models")
        if not self.target_methods or any(not item.strip() for item in self.target_methods):
            raise ValueError("strategy requires non-empty target methods")
        for name, values in (
            ("compatible states", self.compatible_states),
            ("prohibited states", self.prohibited_states),
            ("mandatory evidence", self.mandatory_evidence),
            ("optional evidence", self.optional_evidence),
            ("entry models", self.entry_models),
            ("target methods", self.target_methods),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")


__all__ = [
    "ConfirmationPolicy",
    "MarketStateClassification",
    "PrimaryMarketState",
    "SecondaryMarketCondition",
    "SetupMaturity",
    "StrategyEligibility",
]
