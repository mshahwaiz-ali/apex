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
    """Physical source metadata associated