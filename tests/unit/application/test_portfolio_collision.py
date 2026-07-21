from __future__ import annotations

from dataclasses import replace

from tests.unit.scoring.test_quality_shadow_rollout import _selection

from apex.application.discovery_setup import build_discovery_assessment
from apex.application.portfolio_retention import (
    PortfolioSuppressionReason,
    build_portfolio_retention_audit,
    portfolio_retention_audit_payload,
)
from apex.strategies.contracts import TradeDirection


def _setup():
    assessment = build_discovery_assessment(_selection())
    assert assessment.setup is not None
    return assessment.setup


def _opposing_short(setup, *, candidate_id: str, score: float):
    entry = replace(
        setup.entry,
        maximum_chase_price=setup.entry.lower * 0.995,
    )
    stop = replace(
        setup.stop_loss,
        price=setup.entry.upper * 1.02,
    )
    targets = tuple(
        replace(
            target,
            price=setup.entry.lower * (0.99 - index * 0.005),
        )
        for index, target in enumerate(setup.take_profits)
    )
    return replace(
        setup,
        candidate_id=candidate_id,
        direction=TradeDirection.SHORT,
        confidence_score=score,
        entry=entry,
        stop_loss=stop,
        take_profits=targets,
    )


def test_overlapping_current_long_short_collision_suppresses_weaker() -> None:
    long_setup = replace(
        _setup(),
        candidate_id="long-strong",
        confidence_score=90.0,
        execution_allowed_now=True,
        confirmation_required=False,
        confirmation_complete=True,
    )
    short_setup = _opposing_short(
        long_setup,
        candidate_id="short-weak",
        score=70.0,
    )

    audit = build_portfolio_retention_audit((short_setup, long_setup))

    assert audit.retained_candidate_ids == ("long-strong",)
    short_record = next(record for record in audit.records if record.candidate_id == "short-weak")
    assert short_record.suppression_reason is (
        PortfolioSuppressionReason.OPPOSING_DIRECTION_COLLISION
    )
    assert short_record.retained_candidate_id == "long-strong"


def test_collision_winner_is_input_order_independent() -> None:
    long_setup = replace(
        _setup(),
        candidate_id="long",
        confidence_score=80.0,
        execution_allowed_now=True,
        confirmation_required=False,
        confirmation_complete=True,
    )
    short_setup = _opposing_short(
        long_setup,
        candidate_id="short",
        score=85.0,
    )

    forward = build_portfolio_retention_audit((long_setup, short_setup))
    reverse = build_portfolio_retention_audit((short_setup, long_setup))

    assert forward.retained_candidate_ids == ("short",)
    assert reverse.retained_candidate_ids == ("short",)


def test_non_overlapping_opposing_setups_do_not_collide() -> None:
    long_setup = replace(
        _setup(),
        candidate_id="long",
        confidence_score=90.0,
        execution_allowed_now=True,
        confirmation_required=False,
        confirmation_complete=True,
    )
    short_setup = _opposing_short(
        long_setup,
        candidate_id="short-away",
        score=80.0,
    )
    short_setup = replace(
        short_setup,
        execution_allowed_now=False,
        entry=replace(
            short_setup.entry,
            lower=short_setup.entry.lower * 1.03,
            preferred=short_setup.entry.preferred * 1.03,
            upper=short_setup.entry.upper * 1.03,
            current_price_inside_zone=False,
            maximum_chase_price=short_setup.entry.current_price * 0.99,
        ),
        stop_loss=replace(
            short_setup.stop_loss,
            price=short_setup.entry.upper * 1.05,
        ),
    )

    audit = build_portfolio_retention_audit((long_setup, short_setup))

    assert set(audit.retained_candidate_ids) == {"long", "short-away"}
    assert all(
        record.suppression_reason is not PortfolioSuppressionReason.OPPOSING_DIRECTION_COLLISION
        for record in audit.records
    )


def test_collision_reason_serializes_separately() -> None:
    long_setup = replace(
        _setup(),
        candidate_id="long",
        confidence_score=90.0,
        execution_allowed_now=True,
        confirmation_required=False,
        confirmation_complete=True,
    )
    short_setup = _opposing_short(
        long_setup,
        candidate_id="short",
        score=70.0,
    )

    payload = portfolio_retention_audit_payload(
        build_portfolio_retention_audit((long_setup, short_setup))
    )

    assert payload["collision_suppressed_count"] == 1
    assert payload["duplicate_suppressed_count"] == 0
    records = payload["records"]
    assert isinstance(records, list)
    short_record = next(record for record in records if record["candidate_id"] == "short")
    assert short_record["suppression_reason"] == ("opposing_direction_collision")
