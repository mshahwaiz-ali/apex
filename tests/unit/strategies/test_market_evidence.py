from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.strategies.market_evidence import (
    DataQualityDisposition,
    EvidenceFreshnessPolicy,
    EvidenceRequirement,
    EvidenceState,
    MarketEvidenceKind,
    MarketEvidenceObservation,
    audit_market_evidence,
    audit_market_evidence_set,
)

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
POLICY = EvidenceFreshnessPolicy(
    maximum_age_seconds=30,
    maximum_clock_skew_seconds=2,
)


def _observation(
    *,
    kind: MarketEvidenceKind = MarketEvidenceKind.AGGREGATE_TRADE_IMBALANCE,
    requirement: EvidenceRequirement = EvidenceRequirement.REQUIRED,
    age_seconds: int = 5,
    skew_seconds: int = 0,
    value_available: bool = True,
    synchronization_valid: bool = True,
) -> MarketEvidenceObservation:
    observed_at = NOW - timedelta(seconds=age_seconds)
    return MarketEvidenceObservation(
        kind=kind,
        requirement=requirement,
        observed_at=observed_at,
        source_timestamp=observed_at - timedelta(seconds=skew_seconds),
        value_available=value_available,
        synchronization_valid=synchronization_valid,
    )


def test_fresh_synchronized_evidence_is_available() -> None:
    audit = audit_market_evidence(
        _observation(),
        evaluated_at=NOW,
        policy=POLICY,
    )

    assert audit.state is EvidenceState.AVAILABLE
    assert audit.usable is True
    assert audit.blocks_required_decision is False
    assert audit.age_seconds == 5
    assert audit.clock_skew_seconds == 0


def test_stale_evidence_is_not_usable() -> None:
    audit = audit_market_evidence(
        _observation(age_seconds=31),
        evaluated_at=NOW,
        policy=POLICY,
    )

    assert audit.state is EvidenceState.STALE
    assert audit.blocks_required_decision is True


def test_unsynchronized_evidence_has_precedence_over_staleness() -> None:
    audit = audit_market_evidence(
        _observation(age_seconds=45, skew_seconds=3),
        evaluated_at=NOW,
        policy=POLICY,
    )

    assert audit.state is EvidenceState.UNSYNCHRONIZED


def test_explicit_sequence_failure_marks_evidence_unsynchronized() -> None:
    audit = audit_market_evidence(
        _observation(synchronization_valid=False),
        evaluated_at=NOW,
        policy=POLICY,
    )

    assert audit.state is EvidenceState.UNSYNCHRONIZED


def test_missing_optional_evidence_is_not_negative_evidence() -> None:
    observation = MarketEvidenceObservation(
        kind=MarketEvidenceKind.LIQUIDATION_IMPULSE,
        requirement=EvidenceRequirement.OPTIONAL,
        observed_at=None,
        source_timestamp=None,
        value_available=False,
    )

    audit = audit_market_evidence(
        observation,
        evaluated_at=NOW,
        policy=POLICY,
    )

    assert audit.state is EvidenceState.MISSING
    assert audit.usable is False
    assert audit.blocks_required_decision is False


def test_required_failure_makes_evidence_set_insufficient() -> None:
    observations = (
        _observation(),
        _observation(
            kind=MarketEvidenceKind.PRICE_OPEN_INTEREST_RELATIONSHIP,
            age_seconds=60,
        ),
        _observation(
            kind=MarketEvidenceKind.LIQUIDATION_IMPULSE,
            requirement=EvidenceRequirement.OPTIONAL,
            value_available=False,
        ),
    )
    policies = {observation.kind: POLICY for observation in observations}

    audit = audit_market_evidence_set(
        observations,
        evaluated_at=NOW,
        policies=policies,
    )

    assert audit.disposition is DataQualityDisposition.INSUFFICIENT
    assert audit.required_failures == (MarketEvidenceKind.PRICE_OPEN_INTEREST_RELATIONSHIP,)
    assert audit.optional_failures == (MarketEvidenceKind.LIQUIDATION_IMPULSE,)


def test_optional_failure_only_degrades_evidence_set() -> None:
    observations = (
        _observation(),
        _observation(
            kind=MarketEvidenceKind.DEPTH_IMBALANCE,
            requirement=EvidenceRequirement.OPTIONAL,
            synchronization_valid=False,
        ),
    )
    policies = {observation.kind: POLICY for observation in observations}

    audit = audit_market_evidence_set(
        observations,
        evaluated_at=NOW,
        policies=policies,
    )

    assert audit.disposition is DataQualityDisposition.DEGRADED
    assert audit.required_failures == ()
    assert audit.optional_failures == (MarketEvidenceKind.DEPTH_IMBALANCE,)


def test_all_available_evidence_is_complete() -> None:
    observations = (
        _observation(),
        _observation(
            kind=MarketEvidenceKind.BREAKOUT_ACCEPTANCE_DURATION,
            requirement=EvidenceRequirement.OPTIONAL,
        ),
    )
    policies = {observation.kind: POLICY for observation in observations}

    audit = audit_market_evidence_set(
        observations,
        evaluated_at=NOW,
        policies=policies,
    )

    assert audit.disposition is DataQualityDisposition.COMPLETE
    assert audit.complete is True


def test_duplicate_evidence_kind_is_rejected() -> None:
    observations = (_observation(), _observation())

    with pytest.raises(
        ValueError,
        match="market evidence kinds must be unique",
    ):
        audit_market_evidence_set(
            observations,
            evaluated_at=NOW,
            policies={
                MarketEvidenceKind.AGGREGATE_TRADE_IMBALANCE: POLICY,
            },
        )


def test_missing_policy_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="missing freshness policy",
    ):
        audit_market_evidence_set(
            (_observation(),),
            evaluated_at=NOW,
            policies={},
        )


def test_future_observation_is_rejected() -> None:
    observation = MarketEvidenceObservation(
        kind=MarketEvidenceKind.SPREAD_DETERIORATION,
        requirement=EvidenceRequirement.REQUIRED,
        observed_at=NOW + timedelta(seconds=1),
        source_timestamp=NOW + timedelta(seconds=1),
        value_available=True,
    )

    with pytest.raises(
        ValueError,
        match="evidence observation cannot be from the future",
    ):
        audit_market_evidence(
            observation,
            evaluated_at=NOW,
            policy=POLICY,
        )
