"""Stable registry for public liquidity analyses."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from apex.domain.models import Candle
from apex.liquidity.analysis import LiquidityAnalysisResult, analyze_liquidity
from apex.structure.contracts import StructureAnalysisResult

LiquidityAnalyzer = Callable[[Sequence[Candle], StructureAnalysisResult], LiquidityAnalysisResult]


@dataclass(frozen=True, slots=True)
class LiquidityRegistry:
    """Immutable deterministic registry of liquidity analyzers."""

    entries: tuple[tuple[str, LiquidityAnalyzer], ...]

    def __post_init__(self) -> None:
        names = tuple(name for name, _ in self.entries)
        if any(not name.strip() for name in names):
            raise ValueError("liquidity registry names cannot be empty")
        if len(names) != len(set(names)):
            raise ValueError("liquidity registry names must be unique")

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.entries)

    def get(self, name: str) -> LiquidityAnalyzer:
        for registered_name, analyzer in self.entries:
            if registered_name == name:
                return analyzer
        raise KeyError(name)

    def run(
        self,
        name: str,
        candles: Sequence[Candle],
        structure: StructureAnalysisResult,
    ) -> LiquidityAnalysisResult:
        return self.get(name)(candles, structure)


def create_default_liquidity_registry() -> LiquidityRegistry:
    """Return the stable public liquidity-analysis registry."""

    return LiquidityRegistry((("market_liquidity", analyze_liquidity),))
