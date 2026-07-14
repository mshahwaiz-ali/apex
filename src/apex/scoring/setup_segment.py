"""Canonical identity for setup-specific historical and forward evidence."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from apex.domain import RiskMode, ScannerMode
from apex.risk.contracts import RiskApprovedSetup
from apex.strategies import StrategyType, TradeDirection

_SETUP_SCANNER_MODES = frozenset({ScannerMode.NORMAL, ScannerMode.GAINERS})


@dataclass(frozen=True, slots=True)
class SetupSegmentContext:
    """Typed orchestration dimensions not owned by a risk-approved setup."""

    scanner_type: ScannerMode
    market_regime: str

    def __post_init__(self) -> None:
        if self.scanner_type not in _SETUP_SCANNER_MODES:
            raise ValueError("setup segment scanner type must identify normal or gainers analysis")
        normalized_regime = self.market_regime.strip().lower()
        if not normalized_regime:
            raise ValueError("setup segment market regime cannot be empty")
        object.__setattr__(self, "market_regime", normalized_regime)


@dataclass(frozen=True, slots=True)
class SetupSegmentIdentity:
    """Immutable evidence identity derived from setup and orchestration state."""

    strategy: StrategyType
    symbol: str
    direction: TradeDirection
    risk_mode: RiskMode
    scanner_type: ScannerMode
    market_regime: str
    score_band: str

    def __post_init__(self) -> None:
        normalized_symbol = self.symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("setup segment symbol cannot be empty")
        normalized_regime = self.market_regime.strip().lower()
        if not normalized_regime:
            raise ValueError("setup segment market regime cannot be empty")
        if self.scanner_type not in _SETUP_SCANNER_MODES:
            raise ValueError("setup segment scanner type must identify normal or gainers analysis")
        if not self.score_band.strip():
            raise ValueError("setup segment score band cannot be empty")
        object.__setattr__(self, "symbol", normalized_symbol)
        object.__setattr__(self, "market_regime", normalized_regime)

    @classmethod
    def from_setup(
        cls,
        *,
        setup: RiskApprovedSetup,
        risk_mode: RiskMode,
        context: SetupSegmentContext,
    ) -> SetupSegmentIdentity:
        """Derive identity from actual setup fields and typed orchestration context."""

        return cls(
            strategy=setup.strategy,
            symbol=setup.symbol,
            direction=setup.direction,
            risk_mode=risk_mode,
            scanner_type=context.scanner_type,
            market_regime=context.market_regime,
            score_band=score_band_for(setup.confidence_score),
        )

    def to_dimensions(self) -> Mapping[str, str]:
        """Serialize using the dimension names consumed by evidence contracts."""

        return MappingProxyType(
            {
                "strategy": self.strategy.value,
                "symbol": self.symbol,
                "direction": self.direction.value,
                "risk_mode": self.risk_mode.value,
                "scanner_type": self.scanner_type.value,
                "market_regime": self.market_regime,
                "score_band": self.score_band,
            }
        )


def score_band_for(score: float) -> str:
    """Return the canonical deterministic evidence band for a setup score."""

    if not math.isfinite(score):
        raise ValueError("setup score must be finite")
    if not 0.0 <= score <= 100.0:
        raise ValueError("setup score must be between zero and 100")

    if score < 55.0:
        return "00_54"
    if score < 65.0:
        return "55_64"
    if score < 75.0:
        return "65_74"
    if score < 85.0:
        return "75_84"
    if score < 90.0:
        return "85_89"
    if score < 95.0:
        return "90_94"
    return "95_100"
