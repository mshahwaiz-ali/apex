from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.strategies.aggregate_trade_imbalance import (
    AggregateTradeImbalanceObservation,
    AggregateTradeImbalancePolicy,
    audit_aggregate_trade_imbalance,
)
from apex.strategies.breakout_acceptance import (
    BreakoutAcceptancePolicy,
    BreakoutAcceptanceState,
    BreakoutBarObservation,
    audit_breakout_acceptance,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.depth_imbalance import (
    DepthImbalanceObservation,
    DepthImbalancePolicy,
    audit_depth_imbalance,
)
from apex.strategies.liquidation_impulse import (
    LiquidationImpulseObservation,
    LiquidationImpulsePolicy,
    audit_liquidation_impulse,
)
from apex.strategies.market_evidence import (
    DataQualityDisposition,
    EvidenceFreshnessPolicy,
    EvidenceRequirement,
    EvidenceState,
    MarketEvidenceKind,
    MarketEvidenceObservation,
    audit_market_evidence_set,
)
from apex.strategies.market_evidence_composition import (
    compose_unified_market_evidence,
)
from apex.strategies.market_evidence_decisions import (
    EvidenceDecisionArea,
    EvidenceDecisionImpact,
    build_market_evidence_decision_bundle,
)
from apex.strategies.price_open_interest import (
    PriceOpenInterestObservation,
    PriceOpenInterestPolicy,
    audit_price_open_interest,
)
from apex.strategies.pullback_volume_decay import (
    PullbackVolumeObservation,
    PullbackVolumePolicy,
    audit_pullback_volume_decay,
)
from apex.strategies.spread_deterioration import (
    SpreadDeteriorationObservation,
    SpreadDeteriorationPolicy,
    audit_spread_deterioration,
)

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
FRESHNESS = EvidenceFreshnessPolicy(
    maximum_age_seconds=30,
    maximum_clock_skew_seconds=2,
)


def _evidence_observation(
    kind: MarketEvidenceKind,
    *,
    requirement: EvidenceRequirement,
    age_seconds: int = 5,
    available: bool = True,
) -> MarketEvidenceObservation:
    timestamp = NOW - timedelta(seconds=age_seconds) if available else None
    return MarketEvidenceObservation(
        kind=kind,
        requirement=requirement,
        observed_at=timestamp,
        source_timestamp=timestamp,
        value_available=available,
    )


def _quality(
    *,
    aggregate_age_seconds: int = 5,
    depth_available: bool = True,
    liquidation_available: bool = True,
):
    observations = (
        _evidence_observation(
            MarketEvidenceKind.AGGREGATE_TRADE_IMBALANCE,
            requirement=EvidenceRequirement.REQUIRED,
            age_seconds=aggregate_age_seconds,
        ),
        _evidence_observation(
            MarketEvidenceKind.PRICE_OPEN_INTEREST_RELATIONSHIP,
            requirement=EvidenceRequirement.REQUIRED,
        ),
        _evidence_observation(
            MarketEvidenceKind.BREAKOUT_ACCEPTANCE_DURATION,
            requirement=EvidenceRequirement.REQUIRED,
        ),
        _evidence_observation(
            MarketEvidenceKind.PULLBACK_VOLUME_DECAY,
            requirement=EvidenceRequirement.REQUIRED,
        ),
        _evidence_observation(
            MarketEvidenceKind.SPREAD_DETERIORATION,
            requirement=EvidenceRequirement.REQUIRED,
        ),
        _evidence_observation(
            MarketEvidenceKind.DEPTH_IMBALANCE,
            requirement=EvidenceRequirement.OPTIONAL,
            available=depth_available,
        ),
        _evidence_observation(
            MarketEvidenceKind.LIQUIDATION_IMPULSE,
            requirement=EvidenceRequirement.OPTIONAL,
            available=liquidation_available,
        ),
    )
    return audit_market_evidence_set(
        observations,
        evaluated_at=NOW,
        policies={observation.kind: FRESHNESS for observation in observations},
    )


def _supportive_core():
    return build_market_evidence_decision_bundle(
        trade_imbalance=audit_aggregate_trade_imbalance(
            TradeDirection.LONG,
            AggregateTradeImbalanceObservation(
                aggressive_buy_notional=800.0,
                aggressive_sell_notional=200.0,
                trade_count=100,
                window_seconds=60,
            ),
            policy=AggregateTradeImbalancePolicy(supportive_ratio=0.2),
        ),
        price_open_interest=audit_price_open_interest(
            TradeDirection.LONG,
            PriceOpenInterestObservation(
                start_price=100.0,
                end_price=102.0,
                start_open_interest=1_000.0,
                end_open_interest=1_080.0,
                window_seconds=300,
            ),
            policy=PriceOpenInterestPolicy(),
        ),
        pullback_volume=audit_pullback_volume_decay(
            PullbackVolumeObservation(
                impulse_volume=1_200.0,
                pullback_volume=250.0,
                impulse_bars=4,
                pullback_bars=2,
            ),
            policy=PullbackVolumePolicy(),
        ),
        spread=audit_spread_deterioration(
            SpreadDeteriorationObservation(
                baseline_spread_fraction=0.0005,
                current_spread_fraction=0.0006,
            ),
            policy=SpreadDeteriorationPolicy(),
        ),
    )


def _supportive_depth():
    return audit_depth_imbalance(
        TradeDirection.LONG,
        DepthImbalanceObservation(
            bid_notional=800.0,
            ask_notional=200.0,
            levels_per_side=10,
            window_basis_points=20.0,
        ),
        policy=DepthImbalancePolicy(supportive_ratio=0.2),
    )


def _supportive_liquidations():
    return audit_liquidation_impulse(
        TradeDirection.LONG,
        LiquidationImpulseObservation(
            long_liquidation_notional=200.0,
            short_liquidation_notional=800.0,
            event_count=20,
            window_seconds=60,
        ),
        policy=LiquidationImpulsePolicy(supportive_ratio=0.2),
    )


def test_batch9_exit_gate_full_supportive_stack_is_complete() -> None:
    breakout = audit_breakout_acceptance(
        TradeDirection.LONG,
        100.0,
        (
            BreakoutBarObservation(
                close=101.0,
                high=102.0,
                low=100.5,
                duration_seconds=60,
            ),
            BreakoutBarObservation(
                close=102.0,
                high=103.0,
                low=101.0,
                duration_seconds=60,
            ),
        ),
        policy=BreakoutAcceptancePolicy(
            minimum_consecutive_closes=2,
            minimum_acceptance_seconds=120,
        ),
    )
    audit = compose_unified_market_evidence(
        quality=_quality(),
        core=_supportive_core(),
        depth=_supportive_depth(),
        liquidation=_supportive_liquidations(),
    )

    assert breakout.state is BreakoutAcceptanceState.ACCEPTED
    assert audit.quality.disposition is DataQualityDisposition.COMPLETE
    assert audit.data_sufficient is True
    assert audit.degraded is False
    assert audit.blocks_activation is False
    assert audit.blocks_execution is False
    assert audit.continuation_caution is False
    assert all(
        decision.impact
        in {
            EvidenceDecisionImpact.SUPPORTS,
            EvidenceDecisionImpact.NEUTRAL,
        }
        for decision in audit.decisions.decisions
    )


def test_batch9_exit_gate_optional_absence_only_degrades() -> None:
    audit = compose_unified_market_evidence(
        quality=_quality(
            depth_available=False,
            liquidation_available=False,
        ),
        core=_supportive_core(),
        depth=None,
        liquidation=None,
    )

    assert audit.quality.disposition is DataQualityDisposition.DEGRADED
    assert audit.data_sufficient is True
    assert audit.degraded is True
    assert audit.blocks_activation is False
    assert audit.blocks_execution is False
    assert tuple(decision.source for decision in audit.decisions.decisions[-2:]) == (
        "depth_imbalance",
        "liquidation_impulse",
    )
    assert tuple(decision.impact for decision in audit.decisions.decisions[-2:]) == (
        EvidenceDecisionImpact.UNAVAILABLE,
        EvidenceDecisionImpact.UNAVAILABLE,
    )
    assert all(evidence.state is EvidenceState.MISSING for evidence in audit.quality.evidence[-2:])


def test_batch9_exit_gate_required_stale_data_is_insufficient() -> None:
    audit = compose_unified_market_evidence(
        quality=_quality(aggregate_age_seconds=31),
        core=_supportive_core(),
        depth=_supportive_depth(),
        liquidation=_supportive_liquidations(),
    )

    assert audit.quality.disposition is DataQualityDisposition.INSUFFICIENT
    assert audit.data_sufficient is False
    assert audit.quality.required_failures == (MarketEvidenceKind.AGGREGATE_TRADE_IMBALANCE,)


def test_batch9_exit_gate_decision_areas_are_explicit() -> None:
    audit = compose_unified_market_evidence(
        quality=_quality(),
        core=_supportive_core(),
        depth=_supportive_depth(),
        liquidation=_supportive_liquidations(),
    )

    by_source = {decision.source: decision.area for decision in audit.decisions.decisions}

    assert by_source["aggregate_trade_imbalance"] is EvidenceDecisionArea.ACTIVATION
    assert by_source["price_open_interest_relationship"] is EvidenceDecisionArea.ACTIVATION
    assert by_source["pullback_volume_decay"] is EvidenceDecisionArea.CONTINUATION
    assert by_source["spread_deterioration"] is EvidenceDecisionArea.EXECUTION
    assert by_source["depth_imbalance"] is EvidenceDecisionArea.ACTIVATION
    assert by_source["liquidation_impulse"] is EvidenceDecisionArea.ACTIVATION


def test_batch9_exit_gate_preserves_diagnostic_only_boundary() -> None:
    quality = _quality()
    core = _supportive_core()
    depth = _supportive_depth()
    liquidation = _supportive_liquidations()

    quality_before = quality.evidence
    core_before = core.decisions

    audit = compose_unified_market_evidence(
        quality=quality,
        core=core,
        depth=depth,
        liquidation=liquidation,
    )

    assert quality.evidence is quality_before
    assert core.decisions is core_before
    assert audit.quality is quality
    assert audit.decisions.decisions[: len(core_before)] == core_before
