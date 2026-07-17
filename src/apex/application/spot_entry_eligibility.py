"""Deterministic entry gate for spot structure analysis."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from apex.domain.spot import SpotMarketRegime
from apex.domain.spot_structure import (
    SpotExtensionState,
    SpotRegimeResult,
    SpotStructureResult,
    SpotTrendState,
)


class SpotEntryEligibilityResult(BaseModel):
    """Explain whether a new long-only spot entry may proceed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    eligible: bool
    reasons: tuple[str, ...]


def evaluate_spot_entry_eligibility(
    structure: SpotStructureResult,
    regime: SpotRegimeResult,
) -> SpotEntryEligibilityResult:
    """Block structurally unsafe spot entries before strategy generation."""

    reasons: list[str] = []
    if not regime.allow_new_entries:
        reasons.append(f"market regime {regime.regime.value} blocks new entries")
    if regime.regime in {SpotMarketRegime.RISK_OFF, SpotMarketRegime.CAPITULATION}:
        reasons.append("broad-market downside risk is elevated")
    if structure.extension is SpotExtensionState.TERMINAL:
        reasons.append("terminal higher-timeframe extension rejects a new chase entry")
    if structure.extension is SpotExtensionState.DOWNSIDE_RISK:
        reasons.append("higher-timeframe downside risk rejects a new entry")
    if structure.trend in {
        SpotTrendState.DOWNTREND,
        SpotTrendState.STRONG_DOWNTREND,
    }:
        reasons.append("higher-timeframe trend is bearish")

    if reasons:
        return SpotEntryEligibilityResult(eligible=False, reasons=tuple(reasons))
    return SpotEntryEligibilityResult(
        eligible=True,
        reasons=("structure and broad-market regime permit strategy evaluation",),
    )
