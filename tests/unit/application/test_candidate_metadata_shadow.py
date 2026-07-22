from datetime import UTC, datetime

from apex.application.candidate_metadata_shadow import enrich_candidate_metadata
from apex.strategies import EntryMode, EntryOpportunityHorizon, StrategyType, TradeDirection
from apex.strategies.contracts import (
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
)


def _candidate(*, metadata: dict[str, object] | None = None) -> TradeCandidate:
    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        decision_time=datetime(2026, 1, 1, tzinfo=UTC),
        entry=EntryZone(
            lower=99.5,
            upper=100.5,
            preferred=100.0,
            current_price=102.0,
            distance_from_current=2.0,
            atr_distance=2.0,
            estimated_move_missed=0.0,
            location_quality=0.8,
            mode=EntryMode.PULLBACK,
            rationale=("test entry",),
            horizon=EntryOpportunityHorizon.NEARBY,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=98.0,
            rationale=("test invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=106.0,
                    label="TP1",
                    rationale=("test target",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.8,
            momentum_quality=0.8,
            volume_quality=0.8,
            liquidity_quality=0.8,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(supporting=("test evidence",)),
        metadata={} if metadata is None else metadata,
    )


def test_shadow_metadata_populates_required_timeframe_and_horizon_fields() -> None:
    metadata = enrich_candidate_metadata(_candidate())

    assert metadata["execution_timeframe"] == "5m"
    assert metadata["setup_timeframe"] == "15m"
    assert metadata["invalidation_timeframe"] == "30m"
    assert metadata["target_timeframe"] == "1h"
    assert metadata["decision_atr"] == 1.0
    assert metadata["expected_bars_to_target"] == 6
    assert metadata["lifecycle_model"] == "trend_pullback"
    assert metadata["legacy_context_lane"] == "nearby_structured"
    assert metadata["measured_context_lane"] == "nearby_structured"
    assert metadata["would_change_lane"] is False
    assert metadata["shadow_metadata_authoritative"] is False


def test_shadow_projection_does_not_use_expiry_or_holding_limits() -> None:
    metadata = enrich_candidate_metadata(
        _candidate(
            metadata={
                "activation_expiry_bars": 1,
                "maximum_holding_candles": 1,
                "entry_expiry_seconds": 1,
            }
        )
    )

    assert metadata["expected_bars_to_target"] == 6


def test_existing_candidate_metadata_remains_authoritative() -> None:
    metadata = enrich_candidate_metadata(
        _candidate(
            metadata={
                "execution_timeframe": "3m",
                "setup_timeframe": "5m",
                "decision_atr": 2.0,
                "expected_bars_to_target": 99,
            }
        )
    )

    assert metadata["execution_timeframe"] == "3m"
    assert metadata["setup_timeframe"] == "5m"
    assert metadata["decision_atr"] == 2.0
    assert metadata["expected_bars_to_target"] == 99


def test_mapping_shadow_metadata_covers_geometry_audit_shape() -> None:
    from apex.application.candidate_metadata_shadow import shadow_metadata_from_mapping

    metadata = shadow_metadata_from_mapping(
        {
            "stop_distance": 4.0,
            "stop_distance_atr": 2.0,
            "context_lane": "nearby_structured",
        },
        strategy="momentum_breakout",
        entry_price=100.0,
        target_price=106.0,
    )

    assert metadata["execution_timeframe"] == "3m"
    assert metadata["setup_timeframe"] == "5m"
    assert metadata["decision_atr"] == 2.0
    assert metadata["expected_bars_to_target"] == 3
    assert metadata["measured_context_lane"] == "immediate_tactical"
    assert metadata["would_change_lane"] is True


def test_mapping_shadow_metadata_derives_atr_from_geometry_prices() -> None:
    from apex.application.candidate_metadata_shadow import shadow_metadata_from_mapping

    metadata = shadow_metadata_from_mapping(
        {
            "context_lane": "nearby_structured",
            "selected_entry": 0.05357,
            "executable_stop": 0.054007638526781664,
            "stop_distance_atr": 0.25,
            "tp1_price": 0.04710867014289602,
        },
        strategy="breakout_retest",
        entry_price=0.05357,
        target_price=0.04710867014289602,
    )

    assert metadata["decision_atr"] is not None
    assert metadata["expected_bars_to_target"] == 4
    assert metadata["legacy_context_lane"] == "nearby_structured"
    assert metadata["measured_context_lane"] == "nearby_structured"
    assert metadata["would_change_lane"] is False
    assert metadata["would_change_geometry_result"] is False
