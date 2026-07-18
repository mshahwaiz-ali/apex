from __future__ import annotations

from apex.application.methodology_contracts import (
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
)
from apex.application.methodology_evidence_aggregation import (
    aggregate_evidence_families,
    evidence_family_aggregate_payload,
)
from apex.application.methodology_snapshot import (
    MethodologySnapshot,
    methodology_snapshot_payload,
)


def _observation(
    *,
    family: EvidenceFamily,
    source: str,
    strength: float,
    freshness: float = 1.0,
    group: str,
    effect: EvidenceEffect,
) -> EvidenceObservation:
    return EvidenceObservation(
        family=family,
        source=source,
        normalized_strength=strength,
        freshness=freshness,
        independence_group=group,
        effect=effect,
        reason=f"{source} reason",
    )


def test_correlated_observations_use_only_strongest_group_contribution() -> None:
    observations = (
        _observation(
            family=EvidenceFamily.MOMENTUM,
            source="rsi",
            strength=0.6,
            group="oscillators",
            effect=EvidenceEffect.SUPPORTS,
        ),
        _observation(
            family=EvidenceFamily.MOMENTUM,
            source="stochastic",
            strength=0.8,
            group="oscillators",
            effect=EvidenceEffect.SUPPORTS,
        ),
    )

    aggregate = aggregate_evidence_families(observations)[0]

    assert aggregate.support_score == 0.8
    assert aggregate.observation_count == 2
    assert aggregate.independence_groups == ("oscillators",)
    assert aggregate.strongest_support == "stochastic reason"


def test_independent_groups_combine_without_linear_vote_counting() -> None:
    observations = (
        _observation(
            family=EvidenceFamily.STRUCTURE,
            source="swing_sequence",
            strength=0.5,
            group="market_structure",
            effect=EvidenceEffect.SUPPORTS,
        ),
        _observation(
            family=EvidenceFamily.STRUCTURE,
            source="level_reclaim",
            strength=0.5,
            group="level_behavior",
            effect=EvidenceEffect.SUPPORTS,
        ),
    )

    aggregate = aggregate_evidence_families(observations)[0]

    assert aggregate.support_score == 0.75
    assert aggregate.net_score == 0.75


def test_freshness_weights_support_and_contradiction_separately() -> None:
    observations = (
        _observation(
            family=EvidenceFamily.PARTICIPATION,
            source="volume_expansion",
            strength=0.8,
            freshness=0.5,
            group="volume",
            effect=EvidenceEffect.SUPPORTS,
        ),
        _observation(
            family=EvidenceFamily.PARTICIPATION,
            source="weak_follow_through",
            strength=0.3,
            group="follow_through",
            effect=EvidenceEffect.CONTRADICTS,
        ),
    )

    aggregate = aggregate_evidence_families(observations)[0]

    assert aggregate.support_score == 0.4
    assert aggregate.contradiction_score == 0.3
    assert aggregate.net_score == 0.10000000000000003
    assert aggregate.strongest_contradiction == "weak_follow_through reason"


def test_aggregation_uses_evidence_family_enum_order() -> None:
    observations = (
        _observation(
            family=EvidenceFamily.LIQUIDITY,
            source="sweep",
            strength=0.7,
            group="liquidity",
            effect=EvidenceEffect.SUPPORTS,
        ),
        _observation(
            family=EvidenceFamily.STRUCTURE,
            source="trend",
            strength=0.7,
            group="structure",
            effect=EvidenceEffect.SUPPORTS,
        ),
    )

    aggregates = aggregate_evidence_families(observations)

    assert [item.family for item in aggregates] == [
        EvidenceFamily.STRUCTURE,
        EvidenceFamily.LIQUIDITY,
    ]


def test_snapshot_payload_exposes_family_summary() -> None:
    observation = _observation(
        family=EvidenceFamily.STRUCTURE,
        source="breakout_acceptance",
        strength=0.9,
        group="structure",
        effect=EvidenceEffect.SUPPORTS,
    )
    payload = methodology_snapshot_payload(MethodologySnapshot(evidence=(observation,)))
    summary = payload["evidence_family_summary"]

    assert len(summary) == 1
    assert summary[0] == evidence_family_aggregate_payload(
        aggregate_evidence_families((observation,))[0]
    )
    assert summary[0]["family"] == "structure"
    assert summary[0]["support_score"] == 0.9
