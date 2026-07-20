from __future__ import annotations

import pytest

from apex.strategies.aggregate_trade_imbalance import (
    AggregateTradeImbalanceObservation,
    AggregateTradeImbalancePolicy,
    TradeImbalanceState,
    audit_aggregate_trade_imbalance,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.market_evidence_decisions import (
    EvidenceDecisionArea,
    EvidenceDecisionImpact,
    build_market_evidence_decision_bundle,
)
from apex.strategies.price_open_interest import (
    PriceOpenInterestObservation,
    PriceOpenInterestPolicy,
    PriceOpenInterestState,
    audit_price_open_interest,
)
from apex.strategies.pullback_volume_decay import (
    PullbackVolumeObservation,
    PullbackVolumePolicy,
    PullbackVolumeState,
    audit_pullback_volume_decay,
)
from apex.strategies.spread_deterioration import (
    SpreadDeteriorationObservation,
    SpreadDeteriorationPolicy,
    SpreadDeteriorationState,
    audit_spread_deterioration,
)


def test_trade_imbalance_is_directionally_symmetric() -> None:
    observation = AggregateTradeImbalanceObservation(
        aggressive_buy_notional=700.0,
        aggressive_sell_notional=300.0,
        trade_count=100,
        window_seconds=60,
    )
    policy = AggregateTradeImbalancePolicy(
        minimum_total_notional=100.0,
        supportive_ratio=0.20,
        contradictory_ratio=0.20,
    )

    long_audit = audit_aggregate_trade_imbalance(
        TradeDirection.LONG,
        observation,
        policy=policy,
    )
    short_audit = audit_aggregate_trade_imbalance(
        TradeDirection.SHORT,
        observation,
        policy=policy,
    )

    assert long_audit.state is TradeImbalanceState.SUPPORTIVE
    assert long_audit.signed_imbalance_ratio == pytest.approx(0.4)
    assert short_audit.state is TradeImbalanceState.CONTRADICTORY
    assert short_audit.signed_imbalance_ratio == pytest.approx(-0.4)


def test_trade_imbalance_requires_material_sample() -> None:
    audit = audit_aggregate_trade_imbalance(
        TradeDirection.LONG,
        AggregateTradeImbalanceObservation(
            aggressive_buy_notional=10.0,
            aggressive_sell_notional=5.0,
            trade_count=2,
            window_seconds=60,
        ),
        policy=AggregateTradeImbalancePolicy(minimum_total_notional=100.0),
    )

    assert audit.state is TradeImbalanceState.INSUFFICIENT
    assert audit.usable is False


def test_price_oi_confirms_new_position_growth() -> None:
    audit = audit_price_open_interest(
        TradeDirection.LONG,
        PriceOpenInterestObservation(
            start_price=100.0,
            end_price=102.0,
            start_open_interest=1_000.0,
            end_open_interest=1_050.0,
            window_seconds=300,
        ),
        policy=PriceOpenInterestPolicy(),
    )

    assert audit.state is PriceOpenInterestState.NEW_POSITION_CONFIRMATION
    assert audit.signed_price_change_fraction == pytest.approx(0.02)
    assert audit.open_interest_change_fraction == pytest.approx(0.05)


def test_price_oi_detects_position_build_against_thesis() -> None:
    audit = audit_price_open_interest(
        TradeDirection.LONG,
        PriceOpenInterestObservation(
            start_price=100.0,
            end_price=98.0,
            start_open_interest=1_000.0,
            end_open_interest=1_060.0,
            window_seconds=300,
        ),
        policy=PriceOpenInterestPolicy(),
    )

    assert audit.state is PriceOpenInterestState.POSITION_BUILD_AGAINST_MOVE


def test_price_oi_short_direction_is_symmetric() -> None:
    audit = audit_price_open_interest(
        TradeDirection.SHORT,
        PriceOpenInterestObservation(
            start_price=100.0,
            end_price=98.0,
            start_open_interest=1_000.0,
            end_open_interest=1_050.0,
            window_seconds=300,
        ),
        policy=PriceOpenInterestPolicy(),
    )

    assert audit.state is PriceOpenInterestState.NEW_POSITION_CONFIRMATION


def test_pullback_volume_decay_supports_continuation() -> None:
    audit = audit_pullback_volume_decay(
        PullbackVolumeObservation(
            impulse_volume=1_000.0,
            pullback_volume=200.0,
            impulse_bars=4,
            pullback_bars=2,
        ),
        policy=PullbackVolumePolicy(),
    )

    assert audit.state is PullbackVolumeState.HEALTHY_DECAY
    assert audit.normalized_volume_ratio == pytest.approx(0.4)


def test_pullback_volume_expansion_warns_against_continuation() -> None:
    audit = audit_pullback_volume_decay(
        PullbackVolumeObservation(
            impulse_volume=400.0,
            pullback_volume=500.0,
            impulse_bars=4,
            pullback_bars=4,
        ),
        policy=PullbackVolumePolicy(),
    )

    assert audit.state is PullbackVolumeState.EXPANDING_AGAINST


def test_spread_deterioration_can_block_execution() -> None:
    audit = audit_spread_deterioration(
        SpreadDeteriorationObservation(
            baseline_spread_fraction=0.0005,
            current_spread_fraction=0.0020,
        ),
        policy=SpreadDeteriorationPolicy(
            deterioration_multiple=1.5,
            blocking_multiple=3.0,
            maximum_spread_fraction=0.003,
        ),
    )

    assert audit.state is SpreadDeteriorationState.BLOCKING
    assert audit.blocks_execution is True
    assert audit.spread_multiple == pytest.approx(4.0)


def test_spread_absolute_limit_can_block_before_relative_limit() -> None:
    audit = audit_spread_deterioration(
        SpreadDeteriorationObservation(
            baseline_spread_fraction=0.0020,
            current_spread_fraction=0.0030,
        ),
        policy=SpreadDeteriorationPolicy(
            deterioration_multiple=2.0,
            blocking_multiple=3.0,
            maximum_spread_fraction=0.0025,
        ),
    )

    assert audit.state is SpreadDeteriorationState.BLOCKING


def test_decision_bundle_ties_features_to_explicit_decisions() -> None:
    trade_imbalance = audit_aggregate_trade_imbalance(
        TradeDirection.LONG,
        AggregateTradeImbalanceObservation(
            aggressive_buy_notional=800.0,
            aggressive_sell_notional=200.0,
            trade_count=100,
            window_seconds=60,
        ),
        policy=AggregateTradeImbalancePolicy(supportive_ratio=0.2),
    )
    price_oi = audit_price_open_interest(
        TradeDirection.LONG,
        PriceOpenInterestObservation(
            start_price=100.0,
            end_price=102.0,
            start_open_interest=1_000.0,
            end_open_interest=1_050.0,
            window_seconds=300,
        ),
        policy=PriceOpenInterestPolicy(),
    )
    pullback = audit_pullback_volume_decay(
        PullbackVolumeObservation(
            impulse_volume=1_000.0,
            pullback_volume=200.0,
            impulse_bars=4,
            pullback_bars=2,
        ),
        policy=PullbackVolumePolicy(),
    )
    spread = audit_spread_deterioration(
        SpreadDeteriorationObservation(
            baseline_spread_fraction=0.0005,
            current_spread_fraction=0.0006,
        ),
        policy=SpreadDeteriorationPolicy(),
    )

    bundle = build_market_evidence_decision_bundle(
        trade_imbalance=trade_imbalance,
        price_open_interest=price_oi,
        pullback_volume=pullback,
        spread=spread,
    )

    assert tuple(decision.area for decision in bundle.decisions) == (
        EvidenceDecisionArea.ACTIVATION,
        EvidenceDecisionArea.ACTIVATION,
        EvidenceDecisionArea.CONTINUATION,
        EvidenceDecisionArea.EXECUTION,
    )
    assert all(decision.impact is EvidenceDecisionImpact.SUPPORTS for decision in bundle.decisions)
    assert bundle.blocks_activation is False
    assert bundle.blocks_execution is False
    assert bundle.continuation_caution is False


def test_decision_bundle_reports_independent_activation_execution_and_continuation_risks() -> None:
    trade_imbalance = audit_aggregate_trade_imbalance(
        TradeDirection.LONG,
        AggregateTradeImbalanceObservation(
            aggressive_buy_notional=200.0,
            aggressive_sell_notional=800.0,
            trade_count=100,
            window_seconds=60,
        ),
        policy=AggregateTradeImbalancePolicy(contradictory_ratio=0.2),
    )
    price_oi = audit_price_open_interest(
        TradeDirection.LONG,
        PriceOpenInterestObservation(
            start_price=100.0,
            end_price=98.0,
            start_open_interest=1_000.0,
            end_open_interest=1_060.0,
            window_seconds=300,
        ),
        policy=PriceOpenInterestPolicy(),
    )
    pullback = audit_pullback_volume_decay(
        PullbackVolumeObservation(
            impulse_volume=400.0,
            pullback_volume=600.0,
            impulse_bars=4,
            pullback_bars=4,
        ),
        policy=PullbackVolumePolicy(),
    )
    spread = audit_spread_deterioration(
        SpreadDeteriorationObservation(
            baseline_spread_fraction=0.0005,
            current_spread_fraction=0.0020,
        ),
        policy=SpreadDeteriorationPolicy(blocking_multiple=3.0),
    )

    bundle = build_market_evidence_decision_bundle(
        trade_imbalance=trade_imbalance,
        price_open_interest=price_oi,
        pullback_volume=pullback,
        spread=spread,
    )

    assert bundle.blocks_activation is True
    assert bundle.blocks_execution is True
    assert bundle.continuation_caution is True
    assert tuple(decision.impact for decision in bundle.decisions) == (
        EvidenceDecisionImpact.BLOCKS,
        EvidenceDecisionImpact.BLOCKS,
        EvidenceDecisionImpact.BLOCKS,
        EvidenceDecisionImpact.BLOCKS,
    )


def test_invalid_policy_geometry_is_rejected() -> None:
    with pytest.raises(ValueError, match="healthy ratio must be below adverse ratio"):
        PullbackVolumePolicy(
            healthy_maximum_ratio=1.1,
            adverse_minimum_ratio=1.0,
        )

    with pytest.raises(
        ValueError,
        match="deterioration multiple must be below blocking multiple",
    ):
        SpreadDeteriorationPolicy(
            deterioration_multiple=3.0,
            blocking_multiple=2.0,
        )
