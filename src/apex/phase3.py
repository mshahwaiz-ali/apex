"""Combined deterministic Phase 3 structure and liquidity analysis."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy
from apex.liquidity.analysis import LiquidityAnalysisResult, analyze_liquidity
from apex.structure.analysis import analyze_structure
from apex.structure.contracts import StructureAnalysisResult


@dataclass(frozen=True, slots=True)
class Phase3AnalysisResult:
    """Composable output from the Phase 3 structure and liquidity pipeline."""

    structure: StructureAnalysisResult
    liquidity: LiquidityAnalysisResult


def analyze_phase3(
    candles: Sequence[Candle],
    *,
    left_window: int = 2,
    right_window: int = 2,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
    zone_tolerance: float = 0.002,
) -> Phase3AnalysisResult:
    """Run structure first, then liquidity, with no strategy assumptions."""

    structure = analyze_structure(
        candles,
        left_window=left_window,
        right_window=right_window,
        active_candle_policy=active_candle_policy,
    )
    liquidity = analyze_liquidity(
        candles,
        structure,
        active_candle_policy=active_candle_policy,
        zone_tolerance=zone_tolerance,
    )
    return Phase3AnalysisResult(structure=structure, liquidity=liquidity)
