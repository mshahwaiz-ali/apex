from __future__ import annotations

from dataclasses import replace

from tests.unit.scoring.test_quality_shadow_rollout import _selection

from apex.application.discovery_setup import build_discovery_assessment
from apex.application.portfolio_retention import (
    PortfolioSuppressionReason,
    build_portfolio_retention_audit,
    setup_geometry_fingerprint,
)


def _setup():
    assessment = build_discovery_assessment(_selection())
    assert assessment.setup is not None
    return assessment.setup


def test_geometry_fingerprint_ignores_candidate_identity_and_strategy_label() -> None:
    setup = _setup()
    duplicate = replace(setup, candidate_id="duplicate-id")

    assert setup_geometry_fingerprint(setup) == setup_geometry_fingerprint(duplicate)


def test_tick_size_normalizes_economically_identical_geometry() -> None:
    setup = _setup()
    shifted = replace(
        setup,
        candidate_id="shifted",
        entry=replace(
            setup.entry,
            lower=setup.entry.lower + 0.001,
            preferred=setup.entry.preferred + 0.001,
            upper=setup.entry.upper + 0.001,
        ),
    )

    assert setup_geometry_fingerprint(setup, tick_size=0.01) == setup_geometry_fingerprint(
        shifted, tick_size=0.01
    )


def test_duplicate_geometry_collapses_deterministically_to_higher_score() -> None:
    setup = _setup()
    stronger = replace(setup, candidate_id="stronger", confidence_score=90.0)
    weaker = replace(setup, candidate_id="weaker", confidence_score=70.0)

    audit = build_portfolio_retention_audit((weaker, stronger))

    assert audit.retained_candidate_ids == ("stronger",)
    weaker_record = next(record for record in audit.records if record.candidate_id == "weaker")
    assert weaker_record.suppression_reason is (PortfolioSuppressionReason.DUPLICATE_GEOMETRY)
    assert weaker_record.retained_candidate_id == "stronger"


def test_distinct_lanes_can_coexist() -> None:
    setup = _setup()
    current = replace(
        setup,
        candidate_id="current",
        execution_allowed_now=True,
        confirmation_required=False,
        confirmation_complete=True,
    )
    nearby = replace(
        setup,
        candidate_id="nearby",
        execution_allowed_now=False,
        entry=replace(
            setup.entry,
            lower=setup.entry.lower * 1.02,
            preferred=setup.entry.preferred * 1.02,
            upper=setup.entry.upper * 1.02,
            maximum_chase_price=setup.entry.maximum_chase_price * 1.02,
            current_price_inside_zone=False,
        ),
    )

    audit = build_portfolio_retention_audit((current, nearby))

    assert set(audit.retained_candidate_ids) == {"current", "nearby"}


def test_same_lane_retains_deterministic_best_and_records_reason() -> None:
    setup = _setup()
    best = replace(
        setup,
        candidate_id="best",
        confidence_score=88.0,
    )
    second = replace(
        setup,
        candidate_id="second",
        confidence_score=80.0,
        take_profits=tuple(
            replace(target, price=target.price * 1.001) for target in setup.take_profits
        ),
    )

    audit = build_portfolio_retention_audit((second, best))

    assert audit.retained_candidate_ids == ("best",)
    second_record = next(record for record in audit.records if record.candidate_id == "second")
    assert second_record.suppression_reason is (PortfolioSuppressionReason.LOWER_PRIORITY_SAME_LANE)
    assert second_record.retained_candidate_id == "best"


def test_invalid_tick_size_rejects() -> None:
    setup = _setup()

    try:
        setup_geometry_fingerprint(setup, tick_size=0.0)
    except ValueError as exc:
        assert "tick size must be positive" in str(exc)
    else:
        raise AssertionError("expected invalid tick size to reject")
