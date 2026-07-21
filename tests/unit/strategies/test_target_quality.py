from __future__ import annotations

from apex.strategies.contracts import TargetType
from apex.strategies.target_quality import target_space_quality


def test_distant_projection_is_not_scored_as_perfect_target_quality() -> None:
    quality = target_space_quality(
        current=100.0,
        invalidation=98.0,
        target=110.0,
        target_type=TargetType.EXPANSION,
    )

    assert 0.0 < quality < 0.75


def test_observed_structure_scores_above_equal_distance_projection() -> None:
    structural = target_space_quality(
        current=100.0,
        invalidation=98.0,
        target=104.0,
        target_type=TargetType.STRUCTURAL,
    )
    projected = target_space_quality(
        current=100.0,
        invalidation=98.0,
        target=104.0,
        target_type=TargetType.EXPANSION,
    )

    assert structural > projected


def test_reward_beyond_adequacy_does_not_raise_target_quality() -> None:
    three_r = target_space_quality(
        current=100.0,
        invalidation=98.0,
        target=106.0,
        target_type=TargetType.STRUCTURAL,
    )
    five_r = target_space_quality(
        current=100.0,
        invalidation=98.0,
        target=110.0,
        target_type=TargetType.STRUCTURAL,
    )

    assert five_r < three_r
