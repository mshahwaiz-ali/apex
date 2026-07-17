"""Typed normalization for strategy-candidate evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.contracts import StrategyEvidence


class StrategyEvidenceKind(StrEnum):
    """Canonical evidence categories shared by every strategy."""

    SUPPORTING = "supporting"
    CONTRADICTION = "contradiction"
    WARNING = "warning"
    FEATURE_REFERENCE = "feature_reference"
    STRUCTURE_REFERENCE = "structure_reference"
    LIQUIDITY_REFERENCE = "liquidity_reference"


@dataclass(frozen=True, slots=True)
class NormalizedStrategyEvidence:
    """One deterministic, typed strategy-evidence record."""

    kind: StrategyEvidenceKind
    code: str
    detail: str

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("normalized evidence code cannot be empty")
        if not self.detail.strip():
            raise ValueError("normalized evidence detail cannot be empty")


_EVIDENCE_GROUPS: tuple[tuple[StrategyEvidenceKind, str], ...] = (
    (StrategyEvidenceKind.SUPPORTING, "supporting"),
    (StrategyEvidenceKind.CONTRADICTION, "contradictions"),
    (StrategyEvidenceKind.WARNING, "warnings"),
    (StrategyEvidenceKind.FEATURE_REFERENCE, "feature_references"),
    (StrategyEvidenceKind.STRUCTURE_REFERENCE, "structure_references"),
    (StrategyEvidenceKind.LIQUIDITY_REFERENCE, "liquidity_references"),
)


def normalize_strategy_evidence(
    evidence: StrategyEvidence,
) -> tuple[NormalizedStrategyEvidence, ...]:
    """Normalize evidence in stable category and source order."""

    records: list[NormalizedStrategyEvidence] = []
    for kind, attribute in _EVIDENCE_GROUPS:
        values = getattr(evidence, attribute)
        for index, detail in enumerate(values, start=1):
            records.append(
                NormalizedStrategyEvidence(
                    kind=kind,
                    code=f"{kind.value.upper()}_{index:03d}",
                    detail=detail,
                )
            )
    return tuple(records)


def strategy_evidence_payload(
    evidence: StrategyEvidence,
) -> list[dict[str, str]]:
    """Serialize normalized candidate evidence."""

    return [
        {
            "kind": item.kind.value,
            "code": item.code,
            "detail": item.detail,
        }
        for item in normalize_strategy_evidence(evidence)
    ]


def strategy_evidence_summary(
    evidence: StrategyEvidence,
) -> dict[str, int]:
    """Return counts for every canonical evidence category."""

    records = normalize_strategy_evidence(evidence)
    return {
        kind.value: sum(item.kind is kind for item in records)
        for kind, _attribute in _EVIDENCE_GROUPS
    }
