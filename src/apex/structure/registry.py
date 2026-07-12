"""Stable registry for public structure analyses."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from apex.domain.models import Candle
from apex.structure.analysis import analyze_structure
from apex.structure.contracts import StructureAnalysisResult

StructureAnalyzer = Callable[[Sequence[Candle]], StructureAnalysisResult]


@dataclass(frozen=True, slots=True)
class StructureRegistry:
    """Immutable deterministic registry of structure analyzers."""

    entries: tuple[tuple[str, StructureAnalyzer], ...]

    def __post_init__(self) -> None:
        names = tuple(name for name, _ in self.entries)
        if any(not name.strip() for name in names):
            raise ValueError("structure registry names cannot be empty")
        if len(names) != len(set(names)):
            raise ValueError("structure registry names must be unique")

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.entries)

    def get(self, name: str) -> StructureAnalyzer:
        for registered_name, analyzer in self.entries:
            if registered_name == name:
                return analyzer
        raise KeyError(name)

    def run(self, name: str, candles: Sequence[Candle]) -> StructureAnalysisResult:
        return self.get(name)(candles)


def create_default_structure_registry() -> StructureRegistry:
    """Return the stable public Phase 3 structure registry."""

    return StructureRegistry((("market_structure", analyze_structure),))
