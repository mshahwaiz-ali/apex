"""Unified auxiliary evidence supplied alongside a methodology snapshot."""

from __future__ import annotations

from dataclasses import dataclass

from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_source_bundle import MethodologySourceBundle
from apex.application.methodology_stop_noise_contracts import StopNoiseEvidence


@dataclass(frozen=True, slots=True)
class MethodologyAuxiliaryEvidence:
    """Optional non-snapshot evidence used by shared methodology semantics."""

    source_bundle: MethodologySourceBundle | None = None
    stop_noise: StopNoiseEvidence | None = None

    def validate_for(self, methodology: MethodologySnapshot) -> None:
        """Validate any attached evidence against the canonical snapshot."""

        if self.source_bundle is not None:
            self.source_bundle.validate_for(methodology)


__all__ = ["MethodologyAuxiliaryEvidence"]
