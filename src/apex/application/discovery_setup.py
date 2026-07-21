"""Build discovery-neutral trade plans from selected candidates."""

from __future__ import annotations

from apex.application.discovery_contracts import (
    ActionableEntry,
    ActivationTrigger,
    ActivationTriggerType,
    ConditionalExecutionPlan,
    DiscoveryAssessment,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    PreEntryInvalidation,
    RecommendedOrderIntent,
    StopLoss,
    StopQualityBand,
    TakeProfit,
    TargetRole,
)
from apex.application.methodology_candidate_entry_authority import (
    CandidateEntryAuthority,
    resolve_candidate_entry_authority,
)
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    SymbolOpportunityPortfolio,
    portfolio_from_setups,
)
from apex.application.portfolio_ranking import (
    DEFAULT_PORTFOLIO_RANKING_POLICY,
    PortfolioRankingPolicy,
)
from apex.application.trade_geometry import build_layered_targets, build_stop_geometry
from apex.domain.methodology_contracts import (
    ContinuationState,
    HoldingHorizon,
    RelationshipSeverity,
    TimeframeRelationship,
)
from apex.scoring.contracts import (
    CandidateOutcome,
    CandidateSelectionResult,
    RankedCandidate,
)
from apex.scoring.quality_dimensions import derive_quality_dimensions
from apex.scoring.quality_shadow_rollout import (
    build_quality_shadow_rollout_diagnostics,
)
from apex.scoring.selection import is_entry_status_executable
from apex.strategies import classify_candidate_actionability
from apex.strategies.contracts import (
    EntryMode,
    EntryZone,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.entry_status import EntryStatus

DEFAULT_MAXIMUM_CHASE_PCT = 0.35
DEFAULT_STRUCTURAL_STOP_BUFFER_PCT = 0.10
DEFAULT_STRUCTURAL_STOP_BUFFER_ATR = 0.25

_VALID_DEVELOPING_OUTCOMES = {
    CandidateOutcome.ACCEPTED,
    CandidateOutcome.ACCEPTED_WITH_WARNING,
}
_CONFIRMATION_REQUIRED_MODES = {
    EntryMode.MARKET_NEAR,
    EntryMode.RETEST,
    EntryMode.SWEEP_RECOVERY,
    EntryMode.MOMENTUM_CONTINUATION,
}


def build_discovery_assessment(
    candidate_selection: CandidateSelectionResult,
) -> DiscoveryAssessment:
    """Convert candidate selection into executable and developing setup views."""

    selected = candidate_selection.selected_candidate
    developing = _best_developing_candidate(candidate_selection, selected=selected)
    quality_shadow = build_quality_shadow_rollout_diagnostics(candidate_selection).to_dict()
    if selected is None:
        return DiscoveryAssessment(
            symbol=candidate_selection.symbol,
            decision_time=candidate_selection.decision_time,
            setup=None,
            reasons=(
                candidate_selection.no_trade_reason or "candidate selection produced no setup",
            ),
            developing_setup=(None if developing is None else _build_setup(developing)),
            quality_shadow_diagnostics=quality_shadow,
        )

    return DiscoveryAssessment(
        symbol=candidate_selection.symbol,
        decision_time=candidate_selection.decision_time,
        setup=_build_setup(selected),
        developing_setup=None if developing is None else _build_setup(developing),
        quality_shadow_diagnostics=quality_shadow,
    )


def build_opportunity_portfolio(
    candidate_selection: CandidateSelectionResult,
    *,
    cmp: float,
    analysis_mode: AnalysisMode,
    ranking_policy: PortfolioRankingPolicy = DEFAULT_PORTFOLIO_RANKING_POLICY,
) -> SymbolOpportunityPortfolio:
    """Build a diagnostic portfolio from accepted ranked candidates.

    The legacy selected/developing assessment remains authoritative during the
    compatibility phase. Every accepted ranked candidate that can be represented
    by DiscoverySetup is retained in deterministic portfolio order.
    """

    setups = tuple(
        _build_setup(item)
        for item in candidate_selection.ranked_candidates
        if item.outcome in _VALID_DEVELOPING_OUTCOMES
    )
    return portfolio_from_setups(
        setups,
        symbol=candidate_selection.symbol,
        cmp=cmp,
        analysis_timestamp=candidate_selection.decision_time,
        analysis_mode=analysis_mode,
        ranking_policy=ranking_policy,
    )


def _best_developing_candidate(
    candidate_selection: CandidateSelectionResult,
    *,
    selected: RankedCandidate | None,
) -> RankedCandidate | None:
    selected_id = None if selected is None else selected.scored.candidate_id
    return next(
        (
            item
            for item in candidate_selection.ranked_candidates
            if item.scored.candidate_id != selected_id
            and item.outcome in _VALID_DEVELOPING_OUTCOMES
            and not is_entry_status_executable(classify_candidate_actionability(item.candidate))
        ),
        None,
    )


def _build_setup(ranked: RankedCandidate) -> DiscoverySetup:
    candidate = ranked.candidate
    entry_authority = resolve_candidate_entry_authority(
        candidate.entry,
        candidate.metadata,
    )
    entry_status = classify_candidate_actionability(candidate)
    entry = _entry_zone(candidate.entry, candidate.direction)
    entry_opportunities = tuple(
        _entry_zone(opportunity, candidate.direction)
        for opportunity in candidate.entry_opportunities
    )
    stop = _stop(candidate, preferred_entry=entry_authority.selected_entry)
    runner_qualified, runner_reason = _runner_qualification(candidate)
    targets = _targets(
        candidate,
        stop,
        preferred_entry=entry_authority.selected_entry,
        runner_qualified=runner_qualified,
    )
    lifecycle = candidate.lifecycle
    expiry_seconds = None if lifecycle is None else lifecycle.expires_after_seconds
    return DiscoverySetup(
        symbol=candidate.symbol,
        direction=candidate.direction,
        strategy=candidate.strategy,
        entry_status=entry_status,
        decision_time=candidate.decision_time,
        candidate_id=ranked.scored.candidate_id,
        confidence_score=ranked.final_score,
        entry=entry,
        stop_loss=stop,
        take_profits=targets,
        management_policies=_management_policies(
            targets,
            candidate.strategy,
            runner_qualified=runner_qualified,
        ),
        warnings=tuple(candidate.evidence.warnings),
        quality_dimensions=derive_quality_dimensions(candidate.quality),
        execution_allowed_now=is_entry_status_executable(entry_status),
        entry_opportunities=entry_opportunities,
        setup_expiry_seconds=expiry_seconds,
        setup_expiry_bars=None if lifecycle is None else lifecycle.expires_after_bars,
        setup_expiry_reason=_expiry_reason(candidate),
        trader_headline=_trader_headline(entry_status),
        entry_mode=candidate.entry.mode,
        confirmation_required=candidate.entry.mode in _CONFIRMATION_REQUIRED_MODES,
        confirmation_complete=(
            candidate.metadata.get("entry_confirmation_complete") is True
            and not candidate.provisional
        ),
        provisional=candidate.provisional,
        canonical_actionability=True,
        layered_state=candidate.layered_state,
        methodology_scores=candidate.score_dimensions,
        runner_qualified=runner_qualified,
        runner_qualification_reason=runner_reason,
        conditional_plan=_conditional_plan(
            candidate,
            entry_status=entry_status,
            entry=entry,
            stop=stop,
            entry_authority=entry_authority,
        ),
    )


def _conditional_plan(
    candidate: TradeCandidate,
    *,
    entry_status: EntryStatus,
    entry: ActionableEntry,
    stop: StopLoss,
    entry_authority: CandidateEntryAuthority,
) -> ConditionalExecutionPlan | None:
    if is_entry_status_executable(entry_status):
        return None

    confirmation_timeframe = _confirmation_timeframe(candidate)
    mode = candidate.entry.mode
    if mode in {EntryMode.PULLBACK, EntryMode.SCALED_ENTRY}:
        trigger_kind = ActivationTriggerType.PRICE_TOUCH
        condition = (
            "price enters the predefined entry zone and the setup is revalidated "
            "before order placement"
        )
        order_intent = RecommendedOrderIntent.LIMIT
        conditional_order_eligible = False
    elif mode is EntryMode.RETEST:
        trigger_kind = ActivationTriggerType.RETEST_HOLD
        condition = "price retests the entry zone and demonstrates acceptance before entry"
        order_intent = RecommendedOrderIntent.ALERT_ONLY
        conditional_order_eligible = False
    elif mode is EntryMode.SWEEP_RECOVERY:
        trigger_kind = ActivationTriggerType.RECLAIM_CLOSE
        condition = "price reclaims the preferred level after the liquidity sweep"
        order_intent = RecommendedOrderIntent.ALERT_ONLY
        conditional_order_eligible = False
    elif mode is EntryMode.MOMENTUM_CONTINUATION:
        trigger_kind = ActivationTriggerType.RETEST_HOLD
        condition = (
            "price tests the shallow continuation reference and momentum confirmation renews"
        )
        order_intent = RecommendedOrderIntent.ALERT_ONLY
        conditional_order_eligible = False
    else:
        trigger_kind = ActivationTriggerType.CANDLE_CLOSE
        condition = "the required confirmation closes through the preferred trigger level"
        order_intent = RecommendedOrderIntent.ALERT_ONLY
        conditional_order_eligible = False

    invalidation_condition = (
        "price reaches or closes below structural invalidation before activation"
        if candidate.direction is TradeDirection.LONG
        else "price reaches or closes above structural invalidation before activation"
    )
    return ConditionalExecutionPlan(
        trigger=ActivationTrigger(
            kind=trigger_kind,
            level=entry_authority.trigger_level,
            condition=condition,
            confirmation_timeframe=confirmation_timeframe,
        ),
        pre_entry_invalidation=PreEntryInvalidation(
            price=candidate.invalidation.price,
            condition=invalidation_condition,
            rationale=candidate.invalidation.rationale,
        ),
        conditional_order_eligible=conditional_order_eligible,
        recommended_order_intent=order_intent,
        reason_not_executable_now=_reason_not_executable(entry_status),
        geometry_basis=entry_authority.geometry_owner,
        entry_source=_entry_source(candidate),
        trigger_matches_preferred_entry=(entry_authority.trigger_matches_selected_entry),
        stop_basis="structural_invalidation_buffered_from_candidate_entry",
        targets_basis="strategy_supplied_targets_with_explicit_provenance",
        geometry_is_trigger_relative=(entry_authority.trigger_matches_selected_entry),
    )


def _entry_source(candidate: TradeCandidate) -> str:
    mode = candidate.entry.mode
    if mode is EntryMode.RETEST:
        return {
            "breakout_continuation": "strategy_generated_broken_level_retest",
            "range_reversal": "strategy_generated_range_boundary_retest",
            "trend_pullback": "strategy_generated_structural_level_retest",
        }.get(candidate.strategy.value, "strategy_generated_retest")
    if mode is EntryMode.SWEEP_RECOVERY:
        return "strategy_generated_liquidity_boundary_recovery"
    if mode is EntryMode.PULLBACK:
        return "strategy_generated_pullback_reference"
    if mode is EntryMode.SCALED_ENTRY:
        return "strategy_generated_scaled_entry_zone"
    if mode is EntryMode.MOMENTUM_CONTINUATION:
        return "strategy_generated_momentum_reference"
    return "strategy_generated_market_near_confirmation"


def _confirmation_timeframe(candidate: TradeCandidate) -> str | None:
    for key in ("confirmation_timeframe", "decision_timeframe", "setup_timeframe"):
        value = candidate.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _reason_not_executable(entry_status: EntryStatus) -> str:
    reasons = {
        EntryStatus.PULLBACK_PREFERRED: ("price has not reached the preferred pullback zone"),
        EntryStatus.CONFIRMATION_AT_CMP: (
            "current price is inside the entry zone, but activation confirmation is incomplete"
        ),
        EntryStatus.WATCH_NEAR_ENTRY: (
            "price is approaching the entry zone but activation is incomplete"
        ),
        EntryStatus.LATE_OR_CHASING: ("current price is beyond acceptable entry geometry"),
        EntryStatus.INVALIDATED: "the setup is invalidated and cannot activate",
    }
    return reasons.get(
        entry_status,
        f"{entry_status.value.lower().replace('_', ' ')} is not currently executable",
    )


def _entry_zone(zone: EntryZone, direction: TradeDirection) -> ActionableEntry:
    configured_chase = zone.max_chase_price
    if configured_chase is None:
        offset = zone.preferred * DEFAULT_MAXIMUM_CHASE_PCT / 100.0
        configured_chase = (
            zone.upper + offset if direction is TradeDirection.LONG else zone.lower - offset
        )
    return ActionableEntry(
        lower=zone.lower,
        upper=zone.upper,
        preferred=zone.preferred,
        current_price=zone.current_price,
        maximum_chase_price=configured_chase,
        current_price_inside_zone=zone.lower <= zone.current_price <= zone.upper,
    )


def _stop(
    candidate: TradeCandidate,
    *,
    preferred_entry: float,
) -> StopLoss:
    preferred = preferred_entry
    raw_atr = candidate.metadata.get("decision_atr")
    atr = (
        float(raw_atr)
        if isinstance(raw_atr, int | float) and not isinstance(raw_atr, bool) and raw_atr > 0
        else None
    )
    geometry = build_stop_geometry(
        direction=candidate.direction,
        preferred_entry=preferred,
        invalidation_price=candidate.invalidation.price,
        invalidation_type=candidate.invalidation.kind,
        atr=atr,
        minimum_buffer_pct=DEFAULT_STRUCTURAL_STOP_BUFFER_PCT,
        structural_buffer_atr=DEFAULT_STRUCTURAL_STOP_BUFFER_ATR,
        invalidation_already_buffered=(
            candidate.metadata.get("invalidation_includes_noise_buffer") is True
        ),
        execution_buffer_override=_positive_or_zero_number(
            candidate.metadata.get("execution_buffer")
        ),
    )
    quality_score = max(
        0.0,
        min(
            1.0,
            candidate.quality.structure_quality * 0.65 + candidate.quality.entry_quality * 0.35,
        ),
    )
    quality_band = (
        StopQualityBand.STRONG
        if quality_score >= 0.75
        else StopQualityBand.ACCEPTABLE
        if quality_score >= 0.45
        else StopQualityBand.WEAK
    )
    return StopLoss(
        price=geometry.price,
        distance=geometry.distance,
        distance_pct=geometry.distance_pct,
        rationale=(
            *candidate.invalidation.rationale,
            geometry.buffer_reason,
        ),
        quality_score=quality_score,
        quality_band=quality_band,
        invalidation_type=candidate.invalidation.kind,
        buffer_rationale=geometry.buffer_reason,
        thesis_invalidation_price=candidate.invalidation.price,
        applied_buffer_distance=geometry.buffer,
    )


def _targets(
    candidate: TradeCandidate,
    stop: StopLoss,
    *,
    preferred_entry: float,
    runner_qualified: bool,
) -> tuple[TakeProfit, ...]:
    preferred = preferred_entry
    levels = build_layered_targets(
        direction=candidate.direction,
        preferred_entry=preferred,
        stop_price=stop.price,
        strategy_targets=candidate.targets.levels,
    )
    partials = _partial_close_percentages(len(levels))
    target_timeframe = _target_timeframe(candidate)
    expected_cost_pct = _positive_or_zero_number(candidate.metadata.get("expected_cost_pct"))
    runner_allowed = runner_qualified
    return tuple(
        TakeProfit(
            label=level.label,
            price=level.price,
            reward=abs(level.price - preferred),
            risk_reward=abs(level.price - preferred) / stop.distance,
            rationale=level.rationale,
            partial_close_pct=partial,
            target_type=level.kind,
            purpose=_target_purpose(level.kind, level.label),
            target_basis=_target_basis(level.kind),
            target_timeframe=target_timeframe,
            target_role=_target_role(level.kind, level.label),
            synthetic=False,
            runner_qualified=(
                runner_allowed
                and _target_role(level.kind, level.label) is TargetRole.EXTENSION_CANDIDATE
            ),
            net_risk_reward=_net_risk_reward(
                preferred_entry=preferred,
                target_price=level.price,
                stop_distance=stop.distance,
                expected_cost_pct=expected_cost_pct,
            ),
            expected_cost_pct=expected_cost_pct,
        )
        for level, partial in zip(levels, partials, strict=True)
    )


def _positive_or_zero_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    numeric = float(value)
    return numeric if numeric >= 0.0 else None


def _net_risk_reward(
    *,
    preferred_entry: float,
    target_price: float,
    stop_distance: float,
    expected_cost_pct: float | None,
) -> float | None:
    if expected_cost_pct is None:
        return None
    gross_reward = abs(target_price - preferred_entry)
    cost_distance = preferred_entry * expected_cost_pct / 100.0
    return max(0.0, gross_reward - cost_distance) / stop_distance


def _target_purpose(kind: TargetType, label: str) -> str:
    if kind is TargetType.PARTIAL:
        return "risk-reduction partial"
    if kind is TargetType.EXPANSION:
        return "conditional extension target"
    if label.upper() == "TP1":
        return "first structural objective"
    return "primary structural objective"


def _target_basis(kind: TargetType) -> str:
    return {
        TargetType.STRUCTURAL: "strategy_supplied_structural_level",
        TargetType.LIQUIDITY: "strategy_supplied_liquidity_level",
        TargetType.RANGE: "strategy_supplied_range_boundary",
        TargetType.EXPANSION: "strategy_supplied_expansion_projection",
        TargetType.PARTIAL: "strategy_supplied_partial_objective",
    }[kind]


def _target_role(kind: TargetType, label: str) -> TargetRole:
    if kind is TargetType.EXPANSION:
        return TargetRole.EXTENSION_CANDIDATE
    if label.upper() == "TP1":
        return TargetRole.PRIMARY
    return TargetRole.CONTINUATION


def _target_timeframe(candidate: TradeCandidate) -> str | None:
    for key in (
        "target_timeframe",
        "setup_timeframe",
        "decision_timeframe",
        "confirmation_timeframe",
    ):
        value = candidate.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _expiry_reason(candidate: TradeCandidate) -> str:
    explicit = candidate.entry.expires_after_seconds is not None
    source = (
        "explicit strategy entry expiry" if explicit else "strategy and entry-mode validity policy"
    )
    return f"{source}: {candidate.strategy.value} / {candidate.entry.mode.value}"


def _trader_headline(status: EntryStatus) -> str:
    if status is EntryStatus.READY_NOW:
        return "Strong setup — executable now"
    if status is EntryStatus.AGGRESSIVE_NOW:
        return "Strong setup — aggressive execution possible"
    if status is EntryStatus.PULLBACK_PREFERRED:
        return "Strong setup — pullback/retest/reclaim pending"
    if status is EntryStatus.CONFIRMATION_AT_CMP:
        return "Current-price setup — confirmation required"
    if status is EntryStatus.WATCH_NEAR_ENTRY:
        return "Developing setup — watch only"
    if status in {EntryStatus.LATE_OR_CHASING, EntryStatus.INVALIDATED}:
        return "Late or invalidated setup"
    return "No defensible setup found"


def _partial_close_percentages(count: int) -> tuple[float, ...]:
    if count <= 0:
        raise ValueError("target count must be positive")
    if count > 3:
        raise ValueError("target allocation supports at most three targets")
    if count == 1:
        return (100.0,)
    if count == 2:
        return (50.0, 50.0)
    return (40.0, 35.0, 25.0)


def _runner_is_qualified(candidate: TradeCandidate) -> bool:
    return _runner_qualification(candidate)[0]


def _runner_qualification(candidate: TradeCandidate) -> tuple[bool, str]:
    state = candidate.layered_state
    if state.timeframe_relationship in {
        TimeframeRelationship.COUNTERTREND_SCALP,
        TimeframeRelationship.DIRECT_STRUCTURAL_OPPOSITION,
        TimeframeRelationship.REVERSAL_ATTEMPT,
    }:
        return False, "higher-timeframe relationship forbids runner treatment"
    if state.relationship_severity in {
        RelationshipSeverity.STRONG,
        RelationshipSeverity.CRITICAL,
    }:
        return False, "higher-timeframe conflict severity is too strong"
    if state.continuation_state is not ContinuationState.FRESH_CONTINUATION:
        return False, "continuation is not fresh enough for a runner"
    if state.timeframe_relationship is not TimeframeRelationship.WITH_TREND:
        return False, "runner requires with-trend higher-timeframe alignment"
    if state.holding_horizon not in {
        HoldingHorizon.MULTI_HOUR,
        HoldingHorizon.SWING,
        HoldingHorizon.RUNNER,
    }:
        return False, "holding horizon is too short for runner treatment"
    if candidate.metadata.get("continuation_evidence_complete") is not True:
        return False, "continuation evidence is incomplete"
    return True, "aligned fresh continuation supports runner management"


def _management_policies(
    targets: tuple[TakeProfit, ...],
    strategy: object | None = None,
    *,
    runner_qualified: bool = False,
) -> tuple[ManagementPolicy, ...]:
    first_target = targets[0]
    final_target = targets[-1]
    family = getattr(getattr(strategy, "canonical_family", None), "value", "generic")
    continuation = {
        "trend_pullback": "the governing swing sequence remains intact",
        "break_continuation": "price continues accepting beyond the broken level",
        "break_retest": "the polarity retest remains held",
        "compression_expansion": "range expansion persists outside compression",
        "range_rejection": "price remains accepted inside the range",
        "failed_break_reclaim": "the reclaimed boundary remains held",
        "liquidity_sweep_reversal": "the sweep extreme remains rejected",
    }.get(family, f"price accepts beyond {first_target.label}")
    failure = {
        "trend_pullback": "the governing swing sequence fails",
        "break_continuation": "price accepts back through the broken level",
        "break_retest": "the polarity retest fails",
        "compression_expansion": "price closes back inside compression",
        "range_rejection": "price accepts beyond the rejected range boundary",
        "failed_break_reclaim": "price accepts beyond the failed-break extreme again",
        "liquidity_sweep_reversal": "price accepts beyond the sweep extreme",
    }.get(family, "strategy evidence fails before the final target")
    trailing_action = (
        "trail the qualified runner behind the latest valid structural swing"
        if runner_qualified
        else "do not retain a runner; manage only the declared targets"
    )
    trailing_rationale = (
        ("retain qualified continuation potential without abandoning structure",)
        if runner_qualified
        else ("runner qualification was not earned by the current evidence",)
    )
    return (
        ManagementPolicy(
            kind=ManagementPolicyType.BREAKEVEN,
            trigger=f"{first_target.label} touched or trade reaches 1R",
            action="protect the entry after partial realization",
            rationale=("preserve the confirmed structural edge",),
        ),
        ManagementPolicy(
            kind=ManagementPolicyType.TRAILING,
            trigger=continuation if runner_qualified else f"{final_target.label} reached",
            action=trailing_action,
            rationale=trailing_rationale,
        ),
        ManagementPolicy(
            kind=ManagementPolicyType.TIME_EXIT,
            trigger="the candidate expires without expected activation",
            action="cancel or exit the stale setup",
            rationale=("avoid carrying a thesis beyond its analysis window",),
        ),
        ManagementPolicy(
            kind=ManagementPolicyType.MOMENTUM_FAILURE,
            trigger=f"{failure} before {final_target.label}",
            action="reduce or exit before structural invalidation",
            rationale=("respond when continuation evidence fails",),
        ),
    )


__all__ = [
    "build_discovery_assessment",
    "build_opportunity_portfolio",
]
