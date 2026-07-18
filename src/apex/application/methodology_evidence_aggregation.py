"""Aggregate canonical evidence without double-counting correlated observations."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from apex.application.methodology_contracts import (
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
)


@dataclass(frozen=True, slots=True)
class EvidenceFamilyAggregate:
    family: EvidenceFamily
    support_score: float
    contradiction_score: float
    neutral_score: float
    net_score: float
    independence_groups: tuple[str, ...]
    observation_count: int
    strongest_support: str | None
    strongest_contradiction: str | None

    def __post_init__(self) -> None:
        for name, value in (
            ("support_score", self.support_score),
            ("contradiction_score", self.contradiction_score),
            ("neutral_score", self.neutral_score),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one")
        if not math.isfinite(self.net_score) or not -1.0 <= self.net_score <= 1.0:
            raise ValueError("net_score must be between minus one and one")
        if self.observation_count < 1:
            raise ValueError("evidence aggregate requires observations")
        if not self.independence_groups:
            raise ValueError("evidence aggregate requires independence groups")
        if len(set(self.independence_groups)) != len(self.independence_groups):
            raise ValueError("evidence independence groups must be unique")


def aggregate_evidence_families(
    observations: tuple[EvidenceObservation, ...],
) -> tuple[EvidenceFamilyAggregate, ...]:
    """Summarize evidence by family while capping correlated group contribution.

    Within one family and independence group, only the strongest observation for
    each effect contributes. This prevents several correlated indicators or
    repeated legacy strings from being counted as independent confirmations.
    """

    grouped: dict[
        EvidenceFamily,
        dict[str, dict[EvidenceEffect, EvidenceObservation]],
    ] = defaultdict(lambda: defaultdict(dict))
    for observation in observations:
        effect_bucket = grouped[observation.family][observation.independence_group]
        current = effect_bucket.get(observation.effect)
        contribution = _weighted_strength(observation)
        if current is None or contribution > _weighted_strength(current):
            effect_bucket[observation.effect] = observation

    aggregates: list[EvidenceFamilyAggregate] = []
    for family in EvidenceFamily:
        groups = grouped.get(family)
        if not groups:
            continue
        support = _combine_group_strengths(groups, EvidenceEffect.SUPPORTS)
        contradiction = _combine_group_strengths(groups, EvidenceEffect.CONTRADICTS)
        neutral = _combine_group_strengths(groups, EvidenceEffect.NEUTRAL)
        family_observations = tuple(
            observation
            for effect_bucket in groups.values()
            for observation in effect_bucket.values()
        )
        strongest_support = _strongest_reason(
            family_observations,
            EvidenceEffect.SUPPORTS,
        )
        strongest_contradiction = _strongest_reason(
            family_observations,
            EvidenceEffect.CONTRADICTS,
        )
        rounded_support = round(support, 10)
        rounded_contradiction = round(contradiction, 10)
        aggregates.append(
            EvidenceFamilyAggregate(
                family=family,
                support_score=rounded_support,
                contradiction_score=rounded_contradiction,
                neutral_score=round(neutral, 10),
                net_score=max(
                    -1.0,
                    min(1.0, rounded_support - rounded_contradiction),
                ),
                independence_groups=tuple(sorted(groups)),
                observation_count=sum(
                    1 for observation in observations if observation.family is family
                ),
                strongest_support=strongest_support,
                strongest_contradiction=strongest_contradiction,
            )
        )
    return tuple(aggregates)


def evidence_family_aggregate_payload(
    aggregate: EvidenceFamilyAggregate,
) -> dict[str, Any]:
    return {
        "family": aggregate.family.value,
        "support_score": aggregate.support_score,
        "contradiction_score": aggregate.contradiction_score,
        "neutral_score": aggregate.neutral_score,
        "net_score": aggregate.net_score,
        "independence_groups": list(aggregate.independence_groups),
        "observation_count": aggregate.observation_count,
        "strongest_support": aggregate.strongest_support,
        "strongest_contradiction": aggregate.strongest_contradiction,
    }


def _combine_group_strengths(
    groups: dict[str, dict[EvidenceEffect, EvidenceObservation]],
    effect: EvidenceEffect,
) -> float:
    strengths = [
        _weighted_strength(observation)
        for effect_bucket in groups.values()
        if (observation := effect_bucket.get(effect)) is not None
    ]
    if not strengths:
        return 0.0
    remaining = 1.0
    for strength in strengths:
        remaining *= 1.0 - strength
    return max(0.0, min(1.0, 1.0 - remaining))


def _weighted_strength(observation: EvidenceObservation) -> float:
    return max(
        0.0,
        min(1.0, observation.normalized_strength * observation.freshness),
    )


def _strongest_reason(
    observations: tuple[EvidenceObservation, ...],
    effect: EvidenceEffect,
) -> str | None:
    matching = tuple(item for item in observations if item.effect is effect)
    if not matching:
        return None
    strongest = max(matching, key=_weighted_strength)
    return strongest.reason


__all__ = [
    "EvidenceFamilyAggregate",
    "aggregate_evidence_families",
    "evidence_family_aggregate_payload",
]
