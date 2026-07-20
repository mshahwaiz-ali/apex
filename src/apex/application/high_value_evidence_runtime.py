"""Runtime snapshot for centrally derived high-value evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from apex.application.high_value_evidence_features import (
    PriceOpenInterestRelationship,
    TakerFlowImbalanceProxy,
    derive_price_open_interest_relationship,
    derive_taker_flow_imbalance_proxy,
)


@dataclass(frozen=True, slots=True)
class HighValueEvidenceRuntimeSnapshot:
    """Derived evidence plus explicit fail-closed unavailability reasons."""

    taker_flow_imbalance: TakerFlowImbalanceProxy | None
    price_open_interest: PriceOpenInterestRelationship | None
    unavailable_reasons: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        keys = [key for key, _ in self.unavailable_reasons]
        if len(set(keys)) != len(keys):
            raise ValueError("runtime evidence unavailable reasons must use unique keys")
        if any(not key.strip() or not reason.strip() for key, reason in self.unavailable_reasons):
            raise ValueError("runtime evidence unavailable reasons cannot be empty")

    @property
    def available_features(self) -> tuple[str, ...]:
        features: list[str] = []
        if self.taker_flow_imbalance is not None:
            features.append("taker_flow_imbalance_proxy")
        if self.price_open_interest is not None:
            features.append("price_open_interest_relationship")
        return tuple(features)


def build_high_value_evidence_runtime_snapshot(
    context: Any,
    *,
    as_of: datetime,
) -> HighValueEvidenceRuntimeSnapshot:
    """Build diagnostics-only evidence from the canonical shared strategy context."""

    market_evidence = getattr(context, "market_evidence", None)
    decision_frame = getattr(context, "decision_frame", None)
    unavailable: list[tuple[str, str]] = []

    taker_flow = (
        tuple(getattr(market_evidence, "taker_flow", ())) if market_evidence is not None else ()
    )
    taker_proxy = derive_taker_flow_imbalance_proxy(taker_flow, as_of=as_of)
    if taker_proxy is None:
        unavailable.append(
            (
                "taker_flow_imbalance_proxy",
                _missing_reason(market_evidence, "taker_flow"),
            )
        )

    open_interest = (
        tuple(getattr(market_evidence, "open_interest", ())) if market_evidence is not None else ()
    )
    candles = (
        tuple(getattr(decision_frame, "recent_candles", ())) if decision_frame is not None else ()
    )
    price_oi = derive_price_open_interest_relationship(
        candles,
        open_interest,
        as_of=as_of,
    )
    if price_oi is None:
        unavailable.append(
            (
                "price_open_interest_relationship",
                _price_oi_unavailable_reason(
                    market_evidence=market_evidence,
                    open_interest=open_interest,
                    candles=candles,
                ),
            )
        )

    return HighValueEvidenceRuntimeSnapshot(
        taker_flow_imbalance=taker_proxy,
        price_open_interest=price_oi,
        unavailable_reasons=tuple(sorted(unavailable)),
    )


def high_value_evidence_runtime_payload(
    snapshot: HighValueEvidenceRuntimeSnapshot,
) -> dict[str, object]:
    """Serialize the diagnostics-only runtime snapshot deterministically."""

    taker = snapshot.taker_flow_imbalance
    price_oi = snapshot.price_open_interest
    return {
        "available_features": list(snapshot.available_features),
        "unavailable_reasons": [
            {"feature": feature, "reason": reason}
            for feature, reason in snapshot.unavailable_reasons
        ],
        "taker_flow_imbalance_proxy": (
            None
            if taker is None
            else {
                "buy_volume": taker.buy_volume,
                "sell_volume": taker.sell_volume,
                "imbalance": taker.imbalance,
                "sample_count": taker.sample_count,
                "latest_captured_at": taker.latest_captured_at.isoformat(),
                "source_label": taker.source_label,
            }
        ),
        "price_open_interest_relationship": (
            None
            if price_oi is None
            else {
                "price_change_pct": price_oi.price_change_pct,
                "open_interest_change_pct": price_oi.open_interest_change_pct,
                "price_direction": price_oi.price_direction.value,
                "open_interest_direction": price_oi.open_interest_direction.value,
                "state": price_oi.state.value,
                "start_at": price_oi.start_at.isoformat(),
                "end_at": price_oi.end_at.isoformat(),
                "maximum_alignment_skew_seconds": (price_oi.maximum_alignment_skew_seconds),
                "source_labels": list(price_oi.source_labels),
            }
        ),
    }


def _missing_reason(market_evidence: Any, input_name: str) -> str:
    if market_evidence is None:
        return "market_evidence_unavailable"
    missing_reasons = tuple(getattr(market_evidence, "missing_reasons", ()))
    reasons = sorted(reason for name, reason in missing_reasons if name == input_name)
    return reasons[0] if reasons else f"{input_name}_empty_or_unusable"


def _price_oi_unavailable_reason(
    *,
    market_evidence: Any,
    open_interest: tuple[Any, ...],
    candles: tuple[Any, ...],
) -> str:
    if not candles:
        return "decision_candles_unavailable"
    if len(tuple(item for item in candles if getattr(item, "is_closed", False))) < 2:
        return "insufficient_closed_candles"
    if not open_interest:
        return _missing_reason(market_evidence, "open_interest")
    if len(open_interest) < 2:
        return "insufficient_open_interest_history"
    return "stale_or_unsynchronized_price_open_interest"


__all__ = [
    "HighValueEvidenceRuntimeSnapshot",
    "build_high_value_evidence_runtime_snapshot",
    "high_value_evidence_runtime_payload",
]
