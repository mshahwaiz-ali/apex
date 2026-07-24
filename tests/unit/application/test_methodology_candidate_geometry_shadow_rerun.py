"""Tests for measured-lane shadow geometry selection."""

from apex.application.methodology_candidate_geometry_safety import measured_geometry_lane
from apex.application.opportunity_portfolio import OpportunityLane


class _Entry:
    preferred = 100.0


class _Target:
    def __init__(self, price: float) -> None:
        self.price = price


class _Targets:
    def __init__(self, price: float) -> None:
        self.levels = (_Target(price),)


class _Candidate:
    entry = _Entry()

    def __init__(self, target: float) -> None:
        self.targets = _Targets(target)


def test_measured_lane_preserves_existing_scalp_subtype() -> None:
    lane = measured_geometry_lane(
        _Candidate(102.0),  # type: ignore[arg-type]
        legacy_lane=OpportunityLane.PULLBACK_SCALP,
        decision_atr=1.0,
    )
    assert lane is OpportunityLane.PULLBACK_SCALP


def test_measured_lane_uses_confirmation_policy_for_non_scalp_immediate() -> None:
    lane = measured_geometry_lane(
        _Candidate(102.0),  # type: ignore[arg-type]
        legacy_lane=OpportunityLane.NEARBY_STRUCTURED,
        decision_atr=1.0,
    )
    assert lane is OpportunityLane.CONFIRMATION_SCALP


def test_measured_lane_promotes_out_of_horizon_nearby_target_to_developing() -> None:
    lane = measured_geometry_lane(
        _Candidate(104.0),  # type: ignore[arg-type]
        legacy_lane=OpportunityLane.PULLBACK_SCALP,
        decision_atr=1.0,
    )
    assert lane is OpportunityLane.DEVELOPING


def test_measured_lane_maps_longer_projections() -> None:
    assert (
        measured_geometry_lane(
            _Candidate(106.0),  # type: ignore[arg-type]
            legacy_lane=OpportunityLane.CMP_SCALP,
            decision_atr=1.0,
        )
        is OpportunityLane.DEVELOPING
    )
    assert (
        measured_geometry_lane(
            _Candidate(112.0),  # type: ignore[arg-type]
            legacy_lane=OpportunityLane.NEARBY_STRUCTURED,
            decision_atr=1.0,
        )
        is OpportunityLane.DEVELOPING
    )
    assert (
        measured_geometry_lane(
            _Candidate(125.0),  # type: ignore[arg-type]
            legacy_lane=OpportunityLane.NEARBY_STRUCTURED,
            decision_atr=1.0,
        )
        is OpportunityLane.RUNNER
    )
