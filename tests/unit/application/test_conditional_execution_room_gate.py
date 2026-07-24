from apex.application.discovery_contracts import ActionableEntry, ActivationTriggerType
from apex.application.discovery_setup import _conditional_plan_has_execution_room
from apex.strategies.contracts import TradeDirection


def _entry(*, maximum_chase: float) -> ActionableEntry:
    return ActionableEntry(
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        current_price=100.0,
        maximum_chase_price=maximum_chase,
        current_price_inside_zone=True,
    )


def test_long_close_confirmation_requires_room_above_zone() -> None:
    assert not _conditional_plan_has_execution_room(
        _entry(maximum_chase=101.0),
        direction=TradeDirection.LONG,
        trigger_kind=ActivationTriggerType.CANDLE_CLOSE,
    )
    assert _conditional_plan_has_execution_room(
        _entry(maximum_chase=101.5),
        direction=TradeDirection.LONG,
        trigger_kind=ActivationTriggerType.CANDLE_CLOSE,
    )


def test_short_close_confirmation_requires_room_below_zone() -> None:
    assert not _conditional_plan_has_execution_room(
        _entry(maximum_chase=99.0),
        direction=TradeDirection.SHORT,
        trigger_kind=ActivationTriggerType.CANDLE_CLOSE,
    )
    assert _conditional_plan_has_execution_room(
        _entry(maximum_chase=98.5),
        direction=TradeDirection.SHORT,
        trigger_kind=ActivationTriggerType.CANDLE_CLOSE,
    )


def test_reclaim_and_retest_confirmation_require_execution_room() -> None:
    for trigger_kind in (
        ActivationTriggerType.RECLAIM_CLOSE,
        ActivationTriggerType.RETEST_HOLD,
    ):
        assert not _conditional_plan_has_execution_room(
            _entry(maximum_chase=99.0),
            direction=TradeDirection.SHORT,
            trigger_kind=trigger_kind,
        )


def test_price_touch_can_activate_at_zone_edge() -> None:
    assert _conditional_plan_has_execution_room(
        _entry(maximum_chase=101.0),
        direction=TradeDirection.LONG,
        trigger_kind=ActivationTriggerType.PRICE_TOUCH,
    )
    assert _conditional_plan_has_execution_room(
        _entry(maximum_chase=99.0),
        direction=TradeDirection.SHORT,
        trigger_kind=ActivationTriggerType.PRICE_TOUCH,
    )


def test_monitor_only_selection_outcomes_cannot_authorize_future_activation() -> None:
    from apex.application.discovery_setup import (
        _MONITOR_ONLY_OUTCOMES,
        _VALID_DEVELOPING_OUTCOMES,
    )

    assert _VALID_DEVELOPING_OUTCOMES.isdisjoint(_MONITOR_ONLY_OUTCOMES)
