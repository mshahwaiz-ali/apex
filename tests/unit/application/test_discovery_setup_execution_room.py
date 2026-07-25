from apex.application.discovery_contracts import ActionableEntry, ActivationTriggerType
from apex.application.discovery_setup import _conditional_plan_has_execution_room
from apex.strategies.contracts import TradeDirection


def test_long_confirmation_uses_trigger_level_not_far_zone_boundary() -> None:
    entry = ActionableEntry(
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        current_price=98.0,
        maximum_chase_price=100.5,
        current_price_inside_zone=False,
    )

    assert _conditional_plan_has_execution_room(
        entry,
        direction=TradeDirection.LONG,
        trigger_kind=ActivationTriggerType.CANDLE_CLOSE,
        trigger_level=100.0,
    )


def test_short_confirmation_uses_trigger_level_not_far_zone_boundary() -> None:
    entry = ActionableEntry(
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        current_price=102.0,
        maximum_chase_price=99.5,
        current_price_inside_zone=False,
    )

    assert _conditional_plan_has_execution_room(
        entry,
        direction=TradeDirection.SHORT,
        trigger_kind=ActivationTriggerType.RETEST_HOLD,
        trigger_level=100.0,
    )


def test_long_confirmation_without_post_trigger_room_is_rejected() -> None:
    entry = ActionableEntry(
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        current_price=98.0,
        maximum_chase_price=100.0,
        current_price_inside_zone=False,
    )

    assert not _conditional_plan_has_execution_room(
        entry,
        direction=TradeDirection.LONG,
        trigger_kind=ActivationTriggerType.RECLAIM_CLOSE,
        trigger_level=100.0,
    )


def test_short_confirmation_without_post_trigger_room_is_rejected() -> None:
    entry = ActionableEntry(
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        current_price=102.0,
        maximum_chase_price=100.0,
        current_price_inside_zone=False,
    )

    assert not _conditional_plan_has_execution_room(
        entry,
        direction=TradeDirection.SHORT,
        trigger_kind=ActivationTriggerType.CANDLE_CLOSE,
        trigger_level=100.0,
    )


def test_price_touch_remains_eligible_without_post_confirmation_margin() -> None:
    entry = ActionableEntry(
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        current_price=98.0,
        maximum_chase_price=100.0,
        current_price_inside_zone=False,
    )

    assert _conditional_plan_has_execution_room(
        entry,
        direction=TradeDirection.LONG,
        trigger_kind=ActivationTriggerType.PRICE_TOUCH,
        trigger_level=100.0,
    )
