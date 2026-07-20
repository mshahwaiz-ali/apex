from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.strategies.aggregate_trade_imbalance import (
    AggregateTradeImbalanceObservation,
    AggregateTradeImbalancePolicy,
    audit_aggregate_trade_imbalance,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.depth_imbalance import (
    DepthImbalanceObservation,
    DepthImbalancePolicy,
    DepthImbalanceState,
    audit_depth_imbalance,
)
from apex.strategies.liquidation_impulse import (
    LiquidationImpulseObservation,
    LiquidationImpulsePolicy,
    LiquidationImpulseState,
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


def _core_bundle():
    return build_market_evidence_decision_bundle(
        trade_imbalance=audit_aggregate_trade_imbalance(
            TradeDirection.LONG,
            AggregateTradeImbalanceObservation(
                aggressive_buy_notional=700.0,
                aggressive_sell_notional=300.0,
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
                end_open_interest=1_050.0,
                window_seconds=300,
            ),
            policy=PriceOpenInterestPolicy(),
        ),
        pullback_volume=audit_pullback_volume_decay(
            PullbackVolumeObservation(
                impulse_volume=1_000.0,
                pullback_volume=200.0,
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


def _quality(
    *,
    depth_available: bool = True,
    liquidation_available: bool = True,
    required_stale: bool = False,
):
    observations = (
        MarketEvidenceObservation(
            kind=MarketEvidenceKind.AGGREGATE_TRADE_IMBALANCE,
            requirement=EvidenceRequirement.REQUIRED,
            observed_at=NOW - timedelta(seconds=40 if required_stale else 5),
            source_timestamp=NOW - timedelta(seconds=40 if required_stale else 5),
            value_available=True,
        ),
        MarketEvidenceObservation(
            kind=MarketEvidenceKind.DEPTH_IMBALANCE,
            requirement=EvidenceRequirement.OPTIONAL,
            observed_at=NOW - timedelta(seconds=5) if depth_available else None,
            source_timestamp=NOW - timedelta(seconds=5) if depth_available else None,
            value_available=depth_available,
        ),
        MarketEvidenceObservation(
            kind=MarketEvidenceKind.LIQUIDATION_IMPULSE,
            requirement=EvidenceRequirement.OPTIONAL,
            observed_at=NOW - timedelta(seconds=5) if liquidation_available else None,
            source_timestamp=NOW - timedelta(seconds=5) if liquidation_available else None,
            value_available=liquidation_available,
        ),
    )
    return audit_market_evidence_set(
        observations,
        evaluated_at=NOW,
        policies={observation.kind: FRESHNESS for observation in observations},
    )


def test_depth_imbalance_is_directionally_symmetric() -> None:
    observation = DepthImbalanceObservation(
        bid_notional=700.0,
        ask_notional=300.0,
        levels_per_side=10,
        window_basis_points=20.0,
    )
    policy = DepthImbalancePolicy(
        minimum_total_notional=100.0,
        supportive_ratio=0.2,
        contradictory_ratio=0.2,
    )

    long_audit = audit_depth_imbalance(
        TradeDirection.LONG,
        observation,
        policy=policy,
    )
    short_audit = audit_depth_imbalance(
        TradeDirection.SHORT,
        observation,
        policy=policy,
    )

    assert long_audit.state is DepthImbalanceState.SUPPORTIVE
    assert long_audit.signed_imbalance_ratio == pytest.approx(0.4)
    assert short_audit.state is DepthImbalanceState.CONTRADICTORY
    assert short_audit.signed_imbalance_ratio == pytest.approx(-0.4)


def test_depth_imbalance_requires_material_notional() -> None:
    audit = audit_depth_imbalance(
        TradeDirection.LONG,
        DepthImbalanceObservation(
            bid_notional=10.0,
            ask_notional=5.0,
            levels_per_side=5,
            window_basis_points=10.0,
        ),
        policy=DepthImbalancePolicy(minimum_total_notional=100.0),
    )

    assert audit.state is DepthImbalanceState.INSUFFICIENT
    assert audit.usable is False


def test_liquidation_impulse_supports_long_when_shorts_are_forced_out() -> None:
    audit = audit_liquidation_impulse(
        TradeDirection.LONG,
        LiquidationImpulseObservation(
            long_liquidation_notional=200.0,
            short_liquidation_notional=800.0,
            event_count=20,
            window_seconds=60,
        ),
        policy=LiquidationImpulsePolicy(supportive_ratio=0.2),
    )

    assert audit.state is LiquidationImpulseState.SUPPORTIVE
    assert audit.signed_imbalance_ratio == pytest.approx(0.6)


def test_liquidation_impulse_is_directionally_symmetric() -> None:
    observation = LiquidationImpulseObservation(
        long_liquidation_notional=800.0,
        short_liquidation_notional=200.0,
        event_count=20,
        window_seconds=60,
    )
    policy = LiquidationImpulsePolicy(
        supportive_ratio=0.2,
        contradictory_ratio=0.2,
    )

    long_audit = audit_liquidation_impulse(
        TradeDirection.LONG,
        observation,
        policy=policy,
    )
    short_audit = audit_liquidation_impulse(
        TradeDirection.SHORT,
        observation,
        policy=policy,
    )

    assert long_audit.state is LiquidationImpulseState.CONTRADICTORY
    assert short_audit.state is LiquidationImpulseState.SUPPORTIVE


def test_liquidation_impulse_requires_events_and_notional() -> None:
    audit = audit_liquidation_impulse(
        TradeDirection.LONG,
        LiquidationImpulseObservation(
            long_liquidation_notional=0.0,
            short_liquidation_notional=0.0,
            event_count=0,
            window_seconds=60,
        ),
        policy=LiquidationImpulsePolicy(minimum_total_notional=100.0),
    )

    assert audit.state is LiquidationImpulseState.INSUFFICIENT
    assert audit.usable is False


def test_unified_composition_adds_depth_and_liquidation_decisions() -> None:
    depth = audit_depth_imbalance(
        TradeDirection.LONG,
        DepthImbalanceObservation(
            bid_notional=700.0,
            ask_notional=300.0,
            levels_per_side=10,
            window_basis_points=20.0,
        ),
        policy=DepthImbalancePolicy(supportive_ratio=0.2),
    )
    liquidation = audit_liquidation_impulse(
        TradeDirection.LONG,
        LiquidationImpulseObservation(
            long_liquidation_notional=200.0,
            short_liquidation_notional=800.0,
            event_count=20,
            window_seconds=60,
        ),
        policy=LiquidationImpulsePolicy(supportive_ratio=0.2),
    )

    audit = compose_unified_market_evidence(
        quality=_quality(),
        core=_core_bundle(),
        depth=depth,
        liquidation=liquidation,
    )

    assert audit.quality.disposition is DataQualityDisposition.COMPLETE
    assert audit.data_sufficient is True
    assert audit.degraded is False
    assert tuple(decision.source for decision in audit.decisions.decisions[-2:]) == (
        "depth_imbalance",
        "liquidation_impulse",
    )
    assert all(
        decision.impact is EvidenceDecisionImpact.SUPPORTS
        for decision in audit.decisions.decisions[-2:]
    )


def test_missing_optional_feeds_degrade_without_becoming_negative() -> None:
    audit = compose_unified_market_evidence(
        quality=_quality(depth_available=False, liquidation_available=False),
        core=_core_bundle(),
        depth=None,
        liquidation=None,
    )

    assert audit.quality.disposition is DataQualityDisposition.DEGRADED
    assert audit.degraded is True
    assert audit.data_sufficient is True
    assert audit.blocks_activation is False
    assert tuple(decision.impact for decision in audit.decisions.decisions[-2:]) == (
        EvidenceDecisionImpact.UNAVAILABLE,
        EvidenceDecisionImpact.UNAVAILABLE,
    )
    assert all(evidence.state is EvidenceState.MISSING for evidence in audit.quality.evidence[-2:])


def test_required_stale_data_makes_unified_audit_insufficient() -> None:
    audit = compose_unified_market_evidence(
        quality=_quality(required_stale=True),
        core=_core_bundle(),
        depth=None,
        liquidation=None,
    )

    assert audit.quality.disposition is DataQualityDisposition.INSUFFICIENT
    assert audit.data_sufficient is False


def test_contradictory_optional_inputs_create_caution_not_hard_block() -> None:
    depth = audit_depth_imbalance(
        TradeDirection.LONG,
        DepthImbalanceObservation(
            bid_notional=200.0,
            ask_notional=800.0,
            levels_per_side=10,
            window_basis_points=20.0,
        ),
        policy=DepthImbalancePolicy(contradictory_ratio=0.2),
    )
    liquidation = audit_liquidation_impulse(
        TradeDirection.LONG,
        LiquidationImpulseObservation(
            long_liquidation_notional=800.0,
            short_liquidation_notional=200.0,
            event_count=20,
            window_seconds=60,
        ),
        policy=LiquidationImpulsePolicy(contradictory_ratio=0.2),
    )

    audit = compose_unified_market_evidence(
        quality=_quality(),
        core=_core_bundle(),
        depth=depth,
        liquidation=liquidation,
    )

    assert audit.blocks_activation is False
    assert tuple(decision.impact for decision in audit.decisions.decisions[-2:]) == (
        EvidenceDecisionImpact.CAUTION,
        EvidenceDecisionImpact.CAUTION,
    )


def test_policy_validation_rejects_invalid_ratios() -> None:
    with pytest.raises(ValueError, match="supportive ratio"):
        DepthImbalancePolicy(supportive_ratio=1.1)

    with pytest.raises(ValueError, match="contradictory ratio"):
        LiquidationImpulsePolicy(contradictory_ratio=-0.1)
