"""Combined deterministic structure and liquidity market analysis."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy
from apex.liquidity.analysis import LiquidityAnalysisResult, analyze_liquidity
from apex.structure.analysis import analyze_structure
from apex.structure.contracts import StructureAnalysisResult
from apex.structure.regime import MarketRegime, classify_market_regime


@dataclass(frozen=True, slots=True)
class MarketAnalysisResult:
    """Composable structure, liquidity, and regime analysis output."""

    structure: StructureAnalysisResult
    liquidity: LiquidityAnalysisResult

    @property
    def regime(self) -> MarketRegime:
        """Return the derived strategy-neutral structural market regime."""

        return classify_market_regime(self.structure)


def analyze_structure_and_liquidity(
    candles: Sequence[Candle],
    *,
    left_window: int = 2,
    right_window: int = 2,
    relative_volume: Sequence[float | None] | None = None,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
    zone_tolerance: float = 0.002,
) -> MarketAnalysisResult:
    """Run structure first, then liquidity, with no strategy assumptions."""

    if relative_volume is not None and len(relative_volume) != len(candles):
        raise ValueError("relative_volume length must match candle count")
    structure = analyze_structure(
        candles,
        left_window=left_window,
        right_window=right_window,
        relative_volume=relative_volume,
        active_candle_policy=active_candle_policy,
    )
    liquidity = analyze_liquidity(
        candles,
        structure,
        relative_volume=relative_volume,
        active_candle_policy=active_candle_policy,
        zone_tolerance=zone_tolerance,
    )
    return MarketAnalysisResult(structure=structure, liquidity=liquidity)
