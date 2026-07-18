"""Canonical bundle for physical methodology source data."""

from __future__ import annotations

from dataclasses import dataclass

from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_source_data_contracts import (
    EvidenceSourceReference,
    SourceCandleMetadata,
)


@dataclass(frozen=True, slots=True)
class MethodologySourceBundle:
    """Physical source metadata associated with one methodology snapshot."""

    source_candles: tuple[SourceCandleMetadata, ...] = ()
    evidence_references: tuple[EvidenceSourceReference, ...] = ()
    confirmation_source_id: str | None = None

    def __post_init__(self) -> None:
        source_ids = [item.source_id for item in self.source_candles]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source candle identifiers must be unique")
        reference_keys = [
            (item.evidence_index, item.source_id) for item in self.evidence_references
        ]
        if len(set(reference_keys)) != len(reference_keys):
            raise ValueError("evidence source references must be unique")
        known_ids = set(source_ids)
        if any(item.source_id not in known_ids for item in self.evidence_references):
            raise ValueError(
                "evidence source reference must identify a recorded source candle"
            )
        if self.confirmation_source_id is not None:
            if not self.confirmation_source_id.strip():
                raise ValueError("confirmation source id cannot be empty")
            if self.confirmation_source_id not in known_ids:
                raise ValueError(
                    "confirmation source id must identify a recorded source candle"
                )

    def validate_for(self, methodology: MethodologySnapshot) -> None:
        """Validate evidence indexes against the associated canonical snapshot."""

        if any(
            item.evidence_index >= len(methodology.evidence)
            for item in self.evidence_references
        ):
            raise ValueError("evidence source reference index is outside canonical evidence")

    @property
    def confirmation_source(self) -> SourceCandleMetadata | None:
        """Return the explicitly selected physical confirmation candle."""

        if self.confirmation_source_id is None:
            return None
        return next(
            item
            for item in self.source_candles
            if item.source_id == self.confirmation_source_id
        )


__all__ = ["MethodologySourceBundle"]
