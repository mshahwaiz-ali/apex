"""Selection-level shadow diagnostics with zero decision authority."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from apex.scoring.contracts import CandidateSelectionResult


@dataclass(frozen=True, slots=True)
class CandidateQualityShadowRecord:
    candidate_id: str
    rank: int
    outcome: str
    selected: bool
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("shadow record candidate identity cannot be empty")
        if self.rank < 1:
            raise ValueError("shadow record rank must be positive")
        if not self.outcome.strip():
            raise ValueError("shadow record outcome cannot be empty")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "rank": self.rank,
            "outcome": self.outcome,
            "selected": self.selected,
            "quality": dict(self.payload),
        }


@dataclass(frozen=True, slots=True)
class QualityShadowRolloutDiagnostics:
    symbol: str
    selected_candidate_id: str | None
    candidate_order: tuple[str, ...]
    records: tuple[CandidateQualityShadowRecord, ...]
    shadow_only: bool = True
    version: int = 1

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("shadow rollout symbol cannot be empty")
        if self.version < 1:
            raise ValueError("shadow rollout version must be positive")
        record_ids = tuple(record.candidate_id for record in self.records)
        if record_ids != self.candidate_order:
            raise ValueError("shadow records must preserve authoritative candidate order")
        if len(set(record_ids)) != len(record_ids):
            raise ValueError("shadow rollout candidate identities must be unique")
        if self.selected_candidate_id is not None and self.selected_candidate_id not in record_ids:
            raise ValueError("selected candidate must exist in shadow records")

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "shadow_only": self.shadow_only,
            "symbol": self.symbol,
            "selected_candidate_id": self.selected_candidate_id,
            "candidate_order": list(self.candidate_order),
            "records": [record.to_dict() for record in self.records],
        }


def build_quality_shadow_rollout_diagnostics(
    selection: CandidateSelectionResult,
) -> QualityShadowRolloutDiagnostics:
    # Import lazily to avoid the application/scoring initialization cycle:
    # candidate components depend on application lane measurement, while the
    # application setup layer imports this shadow-only serializer.
    from apex.scoring.candidate_quality_components import (
        candidate_quality_shadow_payload,
    )

    selected_id = (
        None
        if selection.selected_candidate is None
        else selection.selected_candidate.scored.candidate_id
    )
    records: list[CandidateQualityShadowRecord] = []
    for ranked in selection.ranked_candidates:
        payload = candidate_quality_shadow_payload(ranked.candidate)
        if payload is None:
            continue
        candidate_id = ranked.scored.candidate_id
        records.append(
            CandidateQualityShadowRecord(
                candidate_id=candidate_id,
                rank=ranked.rank,
                outcome=ranked.outcome.value,
                selected=candidate_id == selected_id,
                payload=payload,
            )
        )

    candidate_order = tuple(record.candidate_id for record in records)
    effective_selected_id = (
        selected_id if selected_id is not None and selected_id in candidate_order else None
    )
    return QualityShadowRolloutDiagnostics(
        symbol=selection.symbol,
        selected_candidate_id=effective_selected_id,
        candidate_order=candidate_order,
        records=tuple(records),
    )


__all__ = [
    "CandidateQualityShadowRecord",
    "QualityShadowRolloutDiagnostics",
    "build_quality_shadow_rollout_diagnostics",
]
