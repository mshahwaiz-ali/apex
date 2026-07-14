from pathlib import Path

from apex.application.spot_lifecycle import (
    SpotLifecycleEvent,
    SpotLifecycleEventType,
    replay_spot_lifecycle,
)
from apex.application.spot_planning import SpotPlanningRequest, build_spot_plan
from apex.config.spot import load_spot_product_config
from apex.domain.spot import SpotAccountInput, SpotLifecycleState
from apex.domain.spot_strategy import (
    SpotStrategy,
    SpotStrategyCandidate,
    SpotStrategyDecision,
    SpotStrategyEligibility,
)


def _candidate() -> SpotStrategyCandidate:
    return SpotStrategyCandidate(
        strategy=SpotStrategy.HIGHER_TIMEFRAME_TREND_PULLBACK,
        decision=SpotStrategyDecision.APPROVE,
        eligibility=SpotStrategyEligibility.RESEARCH,
        thesis="bullish pullback",
        invalidation_price=90.0,
        evidence=("fixture",),
    )


def test_build_spot_plan_is_bounded_and_cash_funded() -> None:
    config = load_spot_product_config(Path("config/spot.yaml"))
    result = build_spot_plan(
        SpotPlanningRequest(
            candidate=_candidate(),
            account=SpotAccountInput(
                quote_asset="USDT",
                available_quote_balance=1000.0,
                total_spot_equity=1000.0,
                current_spot_exposure=100.0,
                open_position_count=1,
            ),
            current_price=100.0,
            support_price=92.0,
            resistance_price=98.0,
            deeper_support_price=95.0,
            recovery_entry_price=94.0,
            correlated_sector_exposure=50.0,
        ),
        config=config,
    )

    assert len(result.entry_plan.entries) == 3
    assert result.position_plan.capital_allocated <= 200.0
    assert result.position_plan.remaining_quote_reserve >= 300.0
    assert sum(item.sell_percentage for item in result.target_plan.targets) == 100.0
    assert result.lifecycle.state is SpotLifecycleState.WAITING_FOR_ENTRY
    payload = result.position_plan.model_dump()
    assert "leverage" not in payload
    assert "liquidation" not in payload
    assert "margin" not in payload


def test_non_approved_candidate_cannot_be_sized() -> None:
    config = load_spot_product_config(Path("config/spot.yaml"))
    candidate = _candidate().model_copy(update={"decision": SpotStrategyDecision.WATCH})

    try:
        build_spot_plan(
            SpotPlanningRequest(
                candidate=candidate,
                account=SpotAccountInput(
                    quote_asset="USDT",
                    available_quote_balance=1000.0,
                    total_spot_equity=1000.0,
                ),
                current_price=100.0,
                support_price=92.0,
                resistance_price=98.0,
                deeper_support_price=95.0,
                recovery_entry_price=94.0,
            ),
            config=config,
        )
    except ValueError as error:
        assert "approved strategy" in str(error)
    else:
        raise AssertionError("WATCH candidate should not receive an S4 plan")


def test_spot_lifecycle_replay_is_deterministic() -> None:
    events = (
        SpotLifecycleEvent(
            event_type=SpotLifecycleEventType.ENTRY_FILLED,
            label="ENTRY_1",
            quantity=1.0,
        ),
        SpotLifecycleEvent(
            event_type=SpotLifecycleEventType.TARGET_FILLED,
            label="TP1",
            quantity=0.25,
        ),
        SpotLifecycleEvent(event_type=SpotLifecycleEventType.STOP_FILLED),
    )

    first = replay_spot_lifecycle(events, initial_stop_price=90.0)
    second = replay_spot_lifecycle(events, initial_stop_price=90.0)

    assert first == second
    assert first.state is SpotLifecycleState.STOPPED
    assert first.open_quantity == 0.0
    assert first.filled_entry_labels == ("ENTRY_1",)
    assert first.completed_target_labels == ("TP1",)
