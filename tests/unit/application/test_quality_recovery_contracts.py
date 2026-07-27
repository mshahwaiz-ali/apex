from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.application.configuration_identity import resolved_configuration_parameters
from apex.application.quality_contracts import (
    CanonicalMarketSnapshot,
    MarketBehaviorProfile,
    ParameterProvenance,
    ResolvedParameter,
    TimeframeSnapshot,
)


def _timeframe(*, closed_at: datetime) -> TimeframeSnapshot:
    return TimeframeSnapshot(
        timeframe="5m",
        role="entry",
        closed_candle_count=200,
        latest_closed_at=closed_at,
        active_candle_present=True,
        stale=False,
        staleness_seconds=30.0,
        tick_size=0.1,
        step_size=0.001,
        minimum_notional=5.0,
    )


def test_canonical_snapshot_has_stable_identity_and_rejects_future_data() -> None:
    decision_time = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    snapshot = CanonicalMarketSnapshot(
        symbol="BTCUSDT",
        decision_time=decision_time,
        provider="historical_replay",
        timeframes=(_timeframe(closed_at=datetime(2026, 7, 27, 11, 55, tzinfo=UTC)),),
        available_evidence=("funding",),
        missing_evidence=(("open_interest", "unavailable"),),
        execution_cost_profile=(("entry_fee_pct", 0.05),),
    )

    assert len(snapshot.snapshot_id) == 64
    assert snapshot.snapshot_id == snapshot.snapshot_id

    with pytest.raises(ValueError, match="future closed candle"):
        CanonicalMarketSnapshot(
            symbol="BTCUSDT",
            decision_time=decision_time,
            provider="historical_replay",
            timeframes=(_timeframe(closed_at=datetime(2026, 7, 27, 12, 5, tzinfo=UTC)),),
            available_evidence=(),
            missing_evidence=(),
            execution_cost_profile=(),
        )


def test_resolved_parameters_expose_every_configuration_leaf() -> None:
    resolved = resolved_configuration_parameters(
        {
            "methodology_gate_mode": "enforce",
            "geometry_execution": {"entry_fee_pct": 0.05},
            "analysis_timeframes": ["5m", "15m"],
        }
    )

    assert {item.name for item in resolved} == {
        "analysis_timeframes",
        "geometry_execution.entry_fee_pct",
        "methodology_gate_mode",
    }
    assert all(
        item.provenance is ParameterProvenance.EXISTING_PRODUCTION_VALUE for item in resolved
    )


def test_quality_contracts_validate_bounds_and_observe_only_profiles() -> None:
    with pytest.raises(ValueError, match="lower bound"):
        ResolvedParameter(
            name="x",
            base_value=1,
            adjustment_factors=(),
            final_value=1,
            units="count",
            provenance=ParameterProvenance.EMPIRICAL_CANDIDATE,
            bounds=(2.0, 1.0),
            version="v1",
            reason="test",
        )

    profile = MarketBehaviorProfile(
        cohort="directional",
        liquidity_quote_volume_median=1_000_000.0,
        volatility_class="normal",
        volatility_percentile=50.0,
        directional_efficiency=0.5,
        chop_score=0.5,
        wick_noise_score=0.25,
        sample_size=120,
    )
    assert profile.authority == "observe_only"
