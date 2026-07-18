"""Interpret structural invalidation without inventing trigger rules or buffers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class InvalidationSemantics:
    """Public interpretation of canonical and compatibility stop information."""

    canonical_available: bool
    compatibility_price_available: bool
    price: float | None
    rule: str | None
    failure_event: str | None
    volatility_buffer_available: bool
    slippage_available: bool
    authoritative: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_invalidation_semantics(
    setup: DiscoverySetup | None,
    methodology: MethodologySnapshot,
    *,
    native_methodology_available: bool,
) -> InvalidationSemantics:
    """Separate a legacy stop price from a canonical structural failure model."""

    invalidation = methodology.invalidation
    if invalidation is not None:
        canonical_available = True
        price = invalidation.price
        rule = invalidation.rule.value
        failure_event = invalidation.failure_event
        volatility_buffer_available = True
        slippage_available = True
        authoritative = native_methodology_available
        interpretation = (
            "canonical structural invalidation is available with an explicit trigger rule, "
            "failure event, volatility buffer, and execution allowance"
        )
    elif setup is not None:
        canonical_available = False
        price = setup.stop_loss.price
        rule = None
        failure_event = None
        volatility_buffer_available = False
        slippage_available = False
        authoritative = False
        interpretation = (
            "a legacy stop price is available for compatibility, but the structural failure "
            "event and touch, wick, or close trigger rule remain unspecified"
        )
    else:
        canonical_available = False
        price = None
        rule = None
        failure_event = None
        volatility_buffer_available = False
        slippage_available = False
        authoritative = False
        interpretation = "no selected setup or canonical structural invalidation is available"

    return InvalidationSemantics(
        canonical_available=canonical_available,
        compatibility_price_available=setup is not None,
        price=price,
        rule=rule,
        failure_event=failure_event,
        volatility_buffer_available=volatility_buffer_available,
        slippage_available=slippage_available,
        authoritative=authoritative,
        interpretation=interpretation,
        limitations=(
            "stop placement must follow structural failure rather than acceptable loss size",
            "touch, wick, and close invalidation are materially different execution rules",
            "missing volatility and slippage allowances must not be represented as zero",
            "position size must be derived after the invalidation distance is established",
        ),
    )


def invalidation_semantics_payload(semantics: InvalidationSemantics) -> dict[str, Any]:
    """Serialize structural invalidation interpretation."""

    return {
        "canonical_available": semantics.canonical_available,
        "compatibility_price_available": semantics.compatibility_price_available,
        "price": semantics.price,
        "rule": semantics.rule,
        "failure_event": semantics.failure_event,
        "volatility_buffer_available": semantics.volatility_buffer_available,
        "slippage_available": semantics.slippage_available,
        "authoritative": semantics.authoritative,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "InvalidationSemantics",
    "derive_invalidation_semantics",
    "invalidation_semantics_payload",
]
