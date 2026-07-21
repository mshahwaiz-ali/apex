import pytest

from apex.application.discovery_contracts import (
    ActivationTrigger,
    ActivationTriggerType,
    ConditionalExecutionPlan,
    PreEntryInvalidation,
    RecommendedOrderIntent,
)
from apex.application.methodology_candidate_entry_authority import (
    resolve_candidate_entry_authority,
)
from apex.strategies.contracts import EntryMode, EntryZone


def _entry() -> EntryZone:
    return EntryZone(
        lower=98.9,
        upper=99.1,
        preferred=99.0,
        current_price=100.0,
        distance_from_current=0.01,
        atr_distance=0.5,
        estimated_move_missed=0.01,
        location_quality=0.8,
        mode=EntryMode.SCALED_ENTRY,
        rationale=("structural retest zone",),
        max_chase_price=100.2,
        expires_after_seconds=2700,
    )


def test_falls_back_to_candidate_preferred_entry_without_explicit_trigger() -> None:
    authority = resolve_candidate_entry_authority(_entry(), {})

    assert authority.selected_entry == 99.0
    assert authority.trigger_level == 99.0
    assert authority.geometry_owner == "candidate_entry_zone"
    assert authority.trigger_matches_selected_entry is True


def test_preserves_explicit_strategy_trigger_without_using_cmp() -> None:
    authority = resolve_candidate_entry_authority(
        _entry(),
        {
            "entry_geometry_owner": "strategy_structure_level",
            "retest_trigger_level": 99.05,
        },
    )

    assert authority.selected_entry == 99.0
    assert authority.trigger_level == 99.05
    assert authority.trigger_level != _entry().current_price
    assert authority.geometry_owner == "strategy_structure_level"
    assert authority.trigger_matches_selected_entry is False


@pytest.mark.parametrize("trigger", [98.8, 99.2])
def test_rejects_explicit_trigger_outside_authoritative_zone(trigger: float) -> None:
    with pytest.raises(ValueError, match="inside the entry zone"):
        resolve_candidate_entry_authority(
            _entry(),
            {"retest_trigger_level": trigger},
        )


@pytest.mark.parametrize("trigger", [True, "99.0"])
def test_rejects_non_numeric_explicit_trigger(trigger: object) -> None:
    with pytest.raises(ValueError, match="must be numeric"):
        resolve_candidate_entry_authority(
            _entry(),
            {"retest_trigger_level": trigger},  # type: ignore[dict-item]
        )


def test_distinct_trigger_is_serialized_as_non_trigger_relative_geometry() -> None:
    authority = resolve_candidate_entry_authority(
        _entry(),
        {
            "entry_geometry_owner": "strategy_structure_level",
            "retest_trigger_level": 99.05,
        },
    )

    plan = ConditionalExecutionPlan(
        trigger=ActivationTrigger(
            kind=ActivationTriggerType.RETEST_HOLD,
            level=authority.trigger_level,
            condition="retest holds before activation",
        ),
        pre_entry_invalidation=PreEntryInvalidation(
            price=98.0,
            condition="structure fails before activation",
            rationale=("structural invalidation",),
        ),
        conditional_order_eligible=False,
        recommended_order_intent=RecommendedOrderIntent.ALERT_ONLY,
        reason_not_executable_now="confirmation is incomplete",
        geometry_basis=authority.geometry_owner,
        entry_source="strategy_generated_structural_level_retest",
        trigger_matches_preferred_entry=authority.trigger_matches_selected_entry,
        stop_basis="structural_invalidation_buffered_from_selected_entry",
        targets_basis="strategy_supplied_targets_from_selected_entry",
        geometry_is_trigger_relative=authority.trigger_matches_selected_entry,
    )

    assert plan.trigger.level == 99.05
    assert plan.trigger_matches_preferred_entry is False
    assert plan.geometry_is_trigger_relative is False


def test_equal_trigger_remains_trigger_relative() -> None:
    authority = resolve_candidate_entry_authority(_entry(), {})

    assert authority.trigger_matches_selected_entry is True
