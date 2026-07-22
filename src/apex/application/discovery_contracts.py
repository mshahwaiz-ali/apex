"""Discovery-neutral contracts for trade setup construction and analysis."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apex.application.opportunity_portfolio import SymbolOpportunityPortfolio

from apex.application.candidate_ranking import CandidateRankingSnapshot
from apex.application.methodology_auxiliary_evidence import MethodologyAuxiliaryEvidence
from apex.application.methodology_identity import METHODOLOGY_VERSION
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.domain.methodology_contracts import (
    LayeredStateSnapshot,
    ScoreDimensions,
)
from apex.domain.models import Candle
from apex.scoring.quality_dimensions import CandidateQualityDimensions
from apex.strategies.contracts import (
    EntryMode,
    InvalidationType,
    TargetType,
    TradeDirection,
)
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


class StopQualityBand(StrEnum):
    STRONG = "strong"
    ACCEPTABLE = "acceptable"
    WEAK = "weak"


class ManagementPolicyType(StrEnum):
    BREAKEVEN = "breakeven"
    TRAILING = "trailing"
    TIME_EXIT = "time_exit"
    MOMENTUM_FAILURE = "momentum_failure"


class TargetRole(StrEnum):
    PRIMARY = "primary"
    CONTINUATION = "continuation"
    EXTENSION_CANDIDATE = "extension_candidate"


class ActivationTriggerType(StrEnum):
    PRICE_TOUCH = "price_touch"
    CANDLE_CLOSE = "candle_close"
    RETEST_HOLD = "retest_hold"
    RECLAIM_CLOSE = "reclaim_close"


class RecommendedOrderIntent(StrEnum):
    STOP = "stop"
    LIMIT = "limit"
    ALERT_ONLY = "alert_only"


class SetupValidity(StrEnum):
    """Structural validity of the trade thesis."""

    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"


class ExecutionAuthority(StrEnum):
    """What the canonical setup authorizes at the decision time."""

    EXECUTE_NOW = "execute_now"
    CONDITIONAL_FUTURE = "conditional_future"
    MONITOR_ONLY = "monitor_only"
    PROHIBITED = "prohibited"


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _positive(name: str, value: float) -> None:
    _finite(name, value)
    if value <= 0.0:
        raise ValueError(f"{name} must be greater than zero")


@dataclass(frozen=True, slots=True)
class ActionableEntry:
    lower: float
    upper: float
    preferred: float
    current_price: float
    maximum_chase_price: float
    current_price_inside_zone: bool

    def __post_init__(self) -> None:
        for name, value in (
            ("entry lower", self.lower),
            ("entry upper", self.upper),
            ("preferred entry", self.preferred),
            ("current price", self.current_price),
            ("maximum chase price", self.maximum_chase_price),
        ):
            _positive(name, value)
        if self.lower > self.upper:
            raise ValueError("entry lower cannot exceed entry upper")
        if not self.lower <= self.preferred <= self.upper:
            raise ValueError("preferred entry must lie inside the entry zone")
        inside = self.lower <= self.current_price <= self.upper
        if self.current_price_inside_zone is not inside:
            raise ValueError("entry inside-zone flag must match entry bounds")


@dataclass(frozen=True, slots=True)
class StopLoss:
    price: float
    distance: float
    distance_pct: float
    rationale: tuple[str, ...]
    quality_score: float = 0.5
    quality_band: StopQualityBand = StopQualityBand.ACCEPTABLE
    invalidation_type: InvalidationType = InvalidationType.STRUCTURAL
    buffer_rationale: str = ""
    thesis_invalidation_price: float | None = None
    applied_buffer_distance: float = 0.0

    def __post_init__(self) -> None:
        _positive("stop price", self.price)
        _positive("stop distance", self.distance)
        _positive("stop distance percentage", self.distance_pct)
        if not self.rationale:
            raise ValueError("stop rationale cannot be empty")
        _finite("stop quality score", self.quality_score)
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("stop quality score must be between zero and one")
        if self.thesis_invalidation_price is not None:
            _positive("thesis invalidation price", self.thesis_invalidation_price)
        _finite("applied stop buffer distance", self.applied_buffer_distance)
        if self.applied_buffer_distance < 0.0:
            raise ValueError("applied stop buffer distance cannot be negative")


@dataclass(frozen=True, slots=True)
class TakeProfit:
    label: str
    price: float
    reward: float
    risk_reward: float
    rationale: tuple[str, ...]
    partial_close_pct: float = 100.0
    target_type: TargetType = TargetType.STRUCTURAL
    purpose: str = "primary structural objective"
    target_basis: str = "strategy_supplied_structural_level"
    target_timeframe: str | None = None
    target_role: TargetRole = TargetRole.PRIMARY
    synthetic: bool = False
    runner_qualified: bool = False
    net_risk_reward: float | None = None
    expected_cost_pct: float | None = None

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("target label cannot be empty")
        for name, value in (
            ("target price", self.price),
            ("target reward", self.reward),
            ("target risk reward", self.risk_reward),
            ("partial close percentage", self.partial_close_pct),
        ):
            _positive(name, value)
        if self.partial_close_pct > 100.0:
            raise ValueError("partial close percentage cannot exceed 100")
        if not self.rationale:
            raise ValueError("target rationale cannot be empty")
        if not self.purpose.strip():
            raise ValueError("target purpose cannot be empty")
        if not self.target_basis.strip():
            raise ValueError("target basis cannot be empty")
        if self.target_timeframe is not None and not self.target_timeframe.strip():
            raise ValueError("target timeframe cannot be blank")
        if self.synthetic:
            raise ValueError("discovery targets must remain strategy supplied")
        if self.runner_qualified and self.target_role is not TargetRole.EXTENSION_CANDIDATE:
            raise ValueError("runner qualification requires an extension target role")
        if self.net_risk_reward is not None:
            _finite("net target risk reward", self.net_risk_reward)
            if self.net_risk_reward < 0.0:
                raise ValueError("net target risk reward cannot be negative")
        if self.expected_cost_pct is not None:
            _finite("expected target cost percentage", self.expected_cost_pct)
            if self.expected_cost_pct < 0.0:
                raise ValueError("expected target cost percentage cannot be negative")


@dataclass(frozen=True, slots=True)
class ManagementPolicy:
    kind: ManagementPolicyType
    trigger: str
    action: str
    rationale: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.trigger.strip() or not self.action.strip():
            raise ValueError("management policy trigger and action cannot be empty")
        if not self.rationale:
            raise ValueError("management policy rationale cannot be empty")


@dataclass(frozen=True, slots=True)
class ActivationTrigger:
    kind: ActivationTriggerType
    level: float
    condition: str
    confirmation_timeframe: str | None = None

    def __post_init__(self) -> None:
        _positive("activation trigger level", self.level)
        if not self.condition.strip():
            raise ValueError("activation trigger condition cannot be empty")
        if self.confirmation_timeframe is not None and not self.confirmation_timeframe.strip():
            raise ValueError("confirmation timeframe cannot be blank")


@dataclass(frozen=True, slots=True)
class PreEntryInvalidation:
    price: float
    condition: str
    rationale: tuple[str, ...]

    def __post_init__(self) -> None:
        _positive("pre-entry invalidation price", self.price)
        if not self.condition.strip():
            raise ValueError("pre-entry invalidation condition cannot be empty")
        if not self.rationale:
            raise ValueError("pre-entry invalidation rationale cannot be empty")


@dataclass(frozen=True, slots=True)
class ConditionalExecutionPlan:
    trigger: ActivationTrigger
    pre_entry_invalidation: PreEntryInvalidation
    conditional_order_eligible: bool
    recommended_order_intent: RecommendedOrderIntent
    reason_not_executable_now: str
    geometry_basis: str
    entry_source: str
    trigger_matches_preferred_entry: bool
    stop_basis: str
    targets_basis: str
    geometry_is_trigger_relative: bool

    def __post_init__(self) -> None:
        if not self.reason_not_executable_now.strip():
            raise ValueError("conditional plan requires a non-executable reason")
        for name, value in (
            ("geometry basis", self.geometry_basis),
            ("entry source", self.entry_source),
            ("stop basis", self.stop_basis),
            ("targets basis", self.targets_basis),
        ):
            if not value.strip():
                raise ValueError(f"conditional plan {name} cannot be empty")
        if self.geometry_is_trigger_relative and not self.trigger_matches_preferred_entry:
            raise ValueError(
                "trigger-relative geometry requires trigger and preferred entry to match"
            )
        if (
            self.recommended_order_intent is RecommendedOrderIntent.ALERT_ONLY
            and self.conditional_order_eligible
        ):
            raise ValueError("alert-only plans cannot authorize a resting conditional order")
        if (
            self.recommended_order_intent is RecommendedOrderIntent.LIMIT
            and self.trigger.kind is not ActivationTriggerType.PRICE_TOUCH
        ):
            raise ValueError("limit intent requires a predefined price-touch trigger")


@dataclass(frozen=True, slots=True)
class DiscoverySetup:
    symbol: str
    direction: TradeDirection
    strategy: StrategyType
    entry_status: EntryStatus
    decision_time: datetime
    candidate_id: str
    confidence_score: float
    entry: ActionableEntry
    stop_loss: StopLoss
    take_profits: tuple[TakeProfit, ...]
    management_policies: tuple[ManagementPolicy, ...]
    warnings: tuple[str, ...] = ()
    quality_dimensions: CandidateQualityDimensions | None = None
    execution_allowed_now: bool = False
    future_activation_allowed: bool = False
    setup_validity: SetupValidity = SetupValidity.VALID
    execution_authority: ExecutionAuthority = ExecutionAuthority.MONITOR_ONLY
    strategy_version: str = "strategy-contract-v1"
    methodology_version: str = METHODOLOGY_VERSION
    entry_opportunities: tuple[ActionableEntry, ...] = ()
    setup_expiry_seconds: int | None = None
    setup_expiry_bars: int | None = None
    setup_expiry_reason: str = ""
    trader_headline: str = ""
    entry_mode: EntryMode = EntryMode.MARKET_NEAR
    confirmation_required: bool = False
    confirmation_complete: bool = True
    provisional: bool = False
    canonical_actionability: bool = False
    conditional_plan: ConditionalExecutionPlan | None = None
    layered_state: LayeredStateSnapshot = field(default_factory=LayeredStateSnapshot)
    methodology_scores: ScoreDimensions = field(default_factory=ScoreDimensions)
    runner_qualified: bool = False
    runner_qualification_reason: str = "runner not evaluated"

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.candidate_id.strip():
            raise ValueError("symbol and candidate identity cannot be empty")
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("decision time must be timezone-aware")
        _finite("confidence score", self.confidence_score)
        if not 0.0 <= self.confidence_score <= 100.0:
            raise ValueError("confidence score must be between zero and 100")
        if not self.take_profits:
            raise ValueError("discovery setup requires at least one target")
        if not self.management_policies:
            raise ValueError("discovery setup requires management policies")
        if not self.runner_qualification_reason.strip():
            raise ValueError("runner qualification reason cannot be empty")
        if not self.strategy_version.strip() or not self.methodology_version.strip():
            raise ValueError("strategy and methodology versions cannot be empty")
        if self.runner_qualified and not any(
            target.runner_qualified for target in self.take_profits
        ):
            raise ValueError("qualified runner requires a qualified target")
        if self.setup_expiry_seconds is not None and self.setup_expiry_seconds <= 0:
            raise ValueError("setup expiry must be positive when provided")
        if self.setup_expiry_bars is not None and self.setup_expiry_bars <= 0:
            raise ValueError("setup bar expiry must be positive when provided")
        if self.setup_expiry_seconds is not None and not self.setup_expiry_reason.strip():
            raise ValueError("setup expiry reason is required when expiry is provided")
        if self.execution_allowed_now and self.future_activation_allowed:
            raise ValueError("setup cannot authorize current and future execution together")
        if self.execution_allowed_now and self.conditional_plan is not None:
            raise ValueError("executable setup cannot also expose a conditional execution plan")
        if self.future_activation_allowed and self.conditional_plan is None:
            raise ValueError("future-authorized setup requires a conditional execution plan")
        derived_validity = (
            SetupValidity.INVALID
            if self.entry_status is EntryStatus.INVALIDATED
            else self.setup_validity
        )
        expected_authority = (
            ExecutionAuthority.PROHIBITED
            if derived_validity is not SetupValidity.VALID
            else (
                ExecutionAuthority.EXECUTE_NOW
                if self.execution_allowed_now
                else (
                    ExecutionAuthority.CONDITIONAL_FUTURE
                    if self.future_activation_allowed
                    else ExecutionAuthority.MONITOR_ONLY
                )
            )
        )
        # Canonical projections are derived from setup state. This keeps legacy
        # constructors and dataclasses.replace() from carrying stale authority.
        object.__setattr__(self, "setup_validity", derived_validity)
        object.__setattr__(self, "execution_authority", expected_authority)
        partial_total = sum(target.partial_close_pct for target in self.take_profits)
        if not math.isclose(partial_total, 100.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("take-profit partial percentages must sum to 100")
        if self.direction is TradeDirection.LONG:
            if self.entry.maximum_chase_price < self.entry.upper:
                raise ValueError("long chase price must not be below the entry zone")
            if self.stop_loss.price >= self.entry.lower:
                raise ValueError("long stop must be below the entry zone")
            if any(target.price <= self.entry.upper for target in self.take_profits):
                raise ValueError("long targets must be above the entry zone")
        else:
            if self.entry.maximum_chase_price > self.entry.lower:
                raise ValueError("short chase price must not be above the entry zone")
            if self.stop_loss.price <= self.entry.upper:
                raise ValueError("short stop must be above the entry zone")
            if any(target.price >= self.entry.lower for target in self.take_profits):
                raise ValueError("short targets must be below the entry zone")


@dataclass(frozen=True, slots=True)
class DiscoveryAssessment:
    symbol: str
    decision_time: datetime
    setup: DiscoverySetup | None
    reasons: tuple[str, ...] = ()
    developing_setup: DiscoverySetup | None = None
    quality_shadow_diagnostics: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("assessment symbol cannot be empty")
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("decision time must be timezone-aware")
        if self.setup is not None and self.reasons:
            raise ValueError("selected discovery setup cannot also have no-trade reasons")
        if self.setup is None and not self.reasons:
            raise ValueError("no-trade assessment requires a reason")
        if self.quality_shadow_diagnostics is not None:
            object.__setattr__(
                self,
                "quality_shadow_diagnostics",
                dict(self.quality_shadow_diagnostics),
            )
        if self.developing_setup is not None:
            if self.developing_setup.symbol != self.symbol:
                raise ValueError("developing setup symbol must match assessment symbol")
            if self.developing_setup.execution_allowed_now:
                raise ValueError("developing setup must not authorize current execution")
            if (
                self.setup is not None
                and self.developing_setup.candidate_id == self.setup.candidate_id
            ):
                raise ValueError("selected and developing setup identities must differ")


@dataclass(frozen=True, slots=True)
class SymbolAnalysis:
    symbol: str
    generated_at: datetime
    assessment: DiscoveryAssessment
    candidate_count: int
    evaluated_timeframes: tuple[str, ...]
    regime_by_timeframe: Mapping[str, str]
    data_quality_by_timeframe: Mapping[str, Mapping[str, Any]]
    strategy_routing: Mapping[str, Any] | None = None
    phase5_diagnostics: Mapping[str, Any] | None = None
    candidate_ranking: CandidateRankingSnapshot | None = None
    methodology: MethodologySnapshot | None = None
    methodology_auxiliary_evidence: MethodologyAuxiliaryEvidence | None = None
    methodology_gate: Mapping[str, Any] | None = None
    market_intelligence: Mapping[str, Any] | None = None
    historical_edge: Mapping[str, Any] | None = None
    outcome_candles: tuple[Candle, ...] = ()
    opportunity_portfolio: SymbolOpportunityPortfolio | None = None


@dataclass(frozen=True, slots=True)
class ScanResult:
    generated_at: datetime
    analyses: tuple[SymbolAnalysis, ...]
    failures: Mapping[str, str]

    @property
    def approved(self) -> tuple[SymbolAnalysis, ...]:
        return tuple(item for item in self.analyses if item.assessment.setup is not None)
