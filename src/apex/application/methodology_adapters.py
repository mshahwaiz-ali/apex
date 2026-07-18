"""Compatibility adapters from existing Apex contracts to methodology contracts."""

from __future__ import annotations

from apex.application.methodology_contracts import (
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
)
from apex.strategies.contracts import StrategyEvidence


_DEFAULT_STRENGTH = 0.5
_DEFAULT_FRESHNESS = 1.0


def strategy_evidence_observations(
    evidence: StrategyEvidence,
) -> tuple[EvidenceObservation, ...]:
    """Map legacy string evidence into deterministic canonical observations.

    Existing strategies do not yet expose calibrated strength, freshness, or
    independence metadata. The adapter therefore uses neutral defaults and
    explicit legacy independence groups until later phases replace them with
    source-native observations.
    """

    observations: list[EvidenceObservation] = []
    observations.extend(
        _observations(
            values=evidence.supporting,
            family=EvidenceFamily.STRUCTURE,
            source_prefix="legacy_support",
            independence_group="legacy_supporting",
            effect=EvidenceEffect.SUPPORTS,
        )
    )
    observations.extend(
        _observations(
            values=evidence.contradictions,
            family=EvidenceFamily.STRUCTURE,
            source_prefix="legacy_contradiction",
            independence_group="legacy_contradictions",
            effect=EvidenceEffect.CONTRADICTS,
        )
    )
    observations.extend(
        _observations(
            values=evidence.warnings,
            family=EvidenceFamily.DATA_QUALITY,
            source_prefix="legacy_warning",
            independence_group="legacy_warnings",
            effect=EvidenceEffect.NEUTRAL,
        )
    )
    observations.extend(
        _observations(
            values=evidence.feature_references,
            family=EvidenceFamily.MOMENTUM,
            source_prefix="legacy_feature",
            independence_group="legacy_features",
            effect=EvidenceEffect.NEUTRAL,
        )
    )
    observations.extend(
        _observations(
            values=evidence.structure_references,
            family=EvidenceFamily.STRUCTURE,
            source_prefix="legacy_structure",
            independence_group="legacy_structure_references",
            effect=EvidenceEffect.NEUTRAL,
        )
    )
    observations.extend(
        _observations(
            values=evidence.liquidity_references,
            family=EvidenceFamily.LIQUIDITY,
            source_prefix="legacy_liquidity",
            independence_group="legacy_liquidity_references",
            effect=EvidenceEffect.NEUTRAL,
        )
    )
    return tuple(observations)


def _observations(
    *,
    values: tuple[str, ...],
    family: EvidenceFamily,
    source_prefix: str,
    independence_group: str,
    effect: EvidenceEffect,
) -> tuple[EvidenceObservation, ...]:
    return tuple(
        EvidenceObservation(
            family=family,
            source=f"{source_prefix}_{index:03d}",
            normalized_strength=_DEFAULT_STRENGTH,
            freshness=_DEFAULT_FRESHNESS,
            independence_group=independence_group,
            effect=effect,
            reason=value,
        )
        for index, value in enumerate(values, start=1)
    )


__all__ = ["strategy_evidence_observations"]
