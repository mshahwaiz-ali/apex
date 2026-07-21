from __future__ import annotations

import pytest

from apex.application.methodology_lane_horizon import (
    LaneHorizonInput,
    LifecycleModel,
    PriceEntryRelation,
    TriggerState,
    classify_lane_and_horizon,
    lane_horizon_payload,
)
from apex.application.methodology_opportunity_context import (
    HoldingHorizon,
    OpportunityLane,
)
from apex.strategies.strategy_types import StrategyType


def _input(**overrides: object) -> LaneHorizonInput:
    values: dict[str, object] = {
        "strategy": StrategyType.MOMENTUM_BREAKOUT,
        "execution_timeframe_minutes": 5,
        "setup_timeframe_minutes": 5,
        "invalidation_timeframe_minutes": 5,
        "target_timeframe_minutes": 5,
        "atr_normalized_target_distance": 1.0,
        "expected_bars_to_target": 4,
        "price_entry_relation": PriceEntryRelation.INSIDE_ZONE,
        "trigger_state": TriggerState.READY,
        "lifecycle_model": LifecycleModel.SCALP,
        "runner_authority": False,
    }
    values.update(overrides)
    return LaneHorizonInput(**values)  # type: ignore[arg-type]


def test_current_breakout_is_not_automatically_scalp() -> None:
    result = classify_lane_and_horizon(
        _input(
            setup_timeframe_minutes=30,
            target_timeframe_minutes=30,
            expected_bars_to_target=16,
            atr_normalized_target_distance=2.4,
            lifecycle_model=LifecycleModel.STRUCTURED,
        )
    )

    assert result.lane is OpportunityLane.CMP_SCALP
    assert result.holding_horizon is HoldingHorizon.STRUCTURED


def test_nearby_pullback_scalp_stays_scalp() -> None:
    result = classify_lane_and_horizon(
        _input(
            price_entry_relation=PriceEntryRelation.NEAR_ZONE,
            trigger_state=TriggerState.PULLBACK_REQUIRED,
            lifecycle_model=LifecycleModel.SCALP,
        )
    )

    assert result.lane is OpportunityLane.PULLBACK_SCALP
    assert result.holding_horizon is HoldingHorizon.SCALP


def test_confirmation_mode_does_not_define_horizon() -> None:
    result = classify_lane_and_horizon(
        _input(
            setup_timeframe_minutes=30,
            target_timeframe_minutes=60,
            expected_bars_to_target=20,
            atr_normalized_target_distance=2.2,
            trigger_state=TriggerState.CONFIRMATION_REQUIRED,
            lifecycle_model=LifecycleModel.STRUCTURED,
        )
    )

    assert result.lane is OpportunityLane.CONFIRMATION_SCALP
    assert result.holding_horizon is HoldingHorizon.STRUCTURED


def test_cmp_inside_zone_becomes_current_confirmation() -> None:
    result = classify_lane_and_horizon(_input(trigger_state=TriggerState.CONFIRMATION_REQUIRED))

    assert result.lane is OpportunityLane.CONFIRMATION_SCALP
    assert result.current_at_cmp is True


def test_entry_away_from_cmp_stays_nearby() -> None:
    result = classify_lane_and_horizon(
        _input(
            price_entry_relation=PriceEntryRelation.AWAY_FROM_ZONE,
            trigger_state=TriggerState.READY,
            lifecycle_model=LifecycleModel.STRUCTURED,
        )
    )

    assert result.lane is OpportunityLane.NEARBY_STRUCTURED
    assert result.current_at_cmp is False


def test_runner_requires_broader_structural_authority() -> None:
    denied = classify_lane_and_horizon(
        _input(
            lifecycle_model=LifecycleModel.RUNNER,
            expected_bars_to_target=30,
            runner_authority=False,
        )
    )
    allowed = classify_lane_and_horizon(
        _input(
            lifecycle_model=LifecycleModel.RUNNER,
            expected_bars_to_target=30,
            runner_authority=True,
        )
    )

    assert denied.lane is OpportunityLane.DEVELOPING
    assert denied.holding_horizon is HoldingHorizon.STRUCTURED
    assert allowed.lane is OpportunityLane.RUNNER
    assert allowed.holding_horizon is HoldingHorizon.RUNNER


def test_beyond_max_chase_is_not_nearby() -> None:
    result = classify_lane_and_horizon(
        _input(
            price_entry_relation=PriceEntryRelation.BEYOND_MAX_CHASE,
            trigger_state=TriggerState.READY,
        )
    )

    assert result.lane is OpportunityLane.DEVELOPING


def test_expected_bars_are_preserved_in_payload() -> None:
    result = classify_lane_and_horizon(_input(expected_bars_to_target=9))
    payload = lane_horizon_payload(result)

    assert payload["expected_bars_to_target"] == 9
    assert payload["lane"] == "cmp_scalp"
    assert payload["holding_horizon"] == "short"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execution_timeframe_minutes", 0),
        ("setup_timeframe_minutes", 0),
        ("invalidation_timeframe_minutes", 0),
        ("target_timeframe_minutes", 0),
        ("expected_bars_to_target", 0),
        ("atr_normalized_target_distance", 0.0),
    ],
)
def test_invalid_measurements_are_rejected(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        _input(**{field: value})
