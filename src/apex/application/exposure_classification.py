"""Deterministic proposed-exposure classification for account-policy approval."""

from __future__ import annotations

from dataclasses import dataclass

from apex.application.symbols import normalize_market_symbol
from apex.strategies import TradeDirection

_STABLE_QUOTES = frozenset({"USD", "USDC", "USDT"})


@dataclass(frozen=True, slots=True)
class ProposedExposureClassification:
    """Auditable direction and correlation buckets for one proposed trade."""

    symbol: str
    direction_bucket: str
    correlation_bucket: str
    directional_exposure_pct: float
    correlated_exposure_pct: float
    directional_source: str
    correlated_source: str

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "direction_bucket": self.direction_bucket,
            "correlation_bucket": self.correlation_bucket,
            "directional_exposure_pct": self.directional_exposure_pct,
            "correlated_exposure_pct": self.correlated_exposure_pct,
            "directional_source": self.directional_source,
            "correlated_source": self.correlated_source,
        }


def classify_proposed_exposure(
    *,
    symbol: str,
    direction: TradeDirection,
    risk_pct: float,
    directional_override_pct: float | None = None,
    correlated_override_pct: float | None = None,
) -> ProposedExposureClassification:
    """Classify proposed exposure without pretending to know statistical correlation."""

    if risk_pct < 0.0:
        raise ValueError("proposed risk cannot be negative")
    canonical = normalize_market_symbol(symbol)
    _base, quote = canonical.split("/", maxsplit=1)
    directional = risk_pct if directional_override_pct is None else directional_override_pct
    correlation_bucket = "CRYPTO_STABLE_QUOTE" if quote in _STABLE_QUOTES else "CRYPTO_CROSS"
    correlated_default = risk_pct if quote in _STABLE_QUOTES else 0.0
    correlated = correlated_default if correlated_override_pct is None else correlated_override_pct
    for name, value in (
        ("directional exposure", directional),
        ("correlated exposure", correlated),
    ):
        if value < 0.0:
            raise ValueError(f"{name} cannot be negative")
        if value > risk_pct:
            raise ValueError(f"{name} cannot exceed proposed risk")
    return ProposedExposureClassification(
        symbol=canonical,
        direction_bucket=direction.value.upper(),
        correlation_bucket=correlation_bucket,
        directional_exposure_pct=directional,
        correlated_exposure_pct=correlated,
        directional_source="override" if directional_override_pct is not None else "automatic",
        correlated_source="override" if correlated_override_pct is not None else "automatic",
    )
