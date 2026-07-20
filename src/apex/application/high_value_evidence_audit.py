"""Typed audit for high-value market evidence wiring and decision usage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apex.strategies import StrategyContext


class EvidenceCapability(StrEnum):
    AGGREGATE_TRADE_IMBALANCE = "aggregate_trade_imbalance"
    PRICE_OPEN_INTEREST_RELATIONSHIP = "price_open_interest_relationship"
    BREAKOUT_ACCEPTANCE_DURATION = "breakout_acceptance_duration"
    PULLBACK_VOLUME_DECAY = "pullback_volume_decay"
    SPREAD_DETERIORATION = "spread_deterioration"
    DEPTH_IMBALANCE = "depth_imbalance"
    LIQUIDATION_IMPULSE = "liquidation_impulse"


class EvidenceReadiness(StrEnum):
    UNAVAILABLE = "unavailable"
    AVAILABLE_UNUSED = "available_unused"
    DECISION_BOUND_UNGUARDED = "decision_bound_unguarded"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class EvidenceUsageRecord:
    capability: EvidenceCapability
    available: bool
    centrally_derived: bool
    freshness_guarded: bool
    decision_bindings: tuple[str, ...] = ()
    source_labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        bindings = tuple(item.strip() for item in self.decision_bindings)
        sources = tuple(item.strip() for item in self.source_labels)
        if any(not item for item in bindings):
            raise ValueError("decision bindings cannot contain empty labels")
        if any(not item for item in sources):
            raise ValueError("source labels cannot contain empty labels")
        if len(set(bindings)) != len(bindings):
            raise ValueError("decision bindings must be unique")
        if len(set(sources)) != len(sources):
            raise ValueError("source labels must be unique")
        if not self.available and (
            self.centrally_derived
            or self.freshness_guarded
            or self.decision_bindings
            or self.source_labels
        ):
            raise ValueError("unavailable evidence cannot claim wiring or decision usage")
        if self.decision_bindings and not self.available:
            raise ValueError("decision-bound evidence must be available")

    @property
    def readiness(self) -> EvidenceReadiness:
        if not self.available:
            return EvidenceReadiness.UNAVAILABLE
        if not self.decision_bindings:
            return EvidenceReadiness.AVAILABLE_UNUSED
        if not self.centrally_derived or not self.freshness_guarded:
            return EvidenceReadiness.DECISION_BOUND_UNGUARDED
        return EvidenceReadiness.READY


@dataclass(frozen=True, slots=True)
class HighValueEvidenceAudit:
    records: tuple[EvidenceUsageRecord, ...]

    def __post_init__(self) -> None:
        capabilities = tuple(item.capability for item in self.records)
        if len(set(capabilities)) != len(capabilities):
            raise ValueError("evidence audit capabilities must be unique")

    @property
    def ready_capabilities(self) -> tuple[EvidenceCapability, ...]:
        return tuple(
            item.capability for item in self.records if item.readiness is EvidenceReadiness.READY
        )

    @property
    def incomplete_capabilities(self) -> tuple[EvidenceCapability, ...]:
        return tuple(
            item.capability
            for item in self.records
            if item.readiness is not EvidenceReadiness.READY
        )


def build_current_high_value_evidence_audit(
    context: StrategyContext,
) -> HighValueEvidenceAudit:
    """Inventory current source availability without claiming decision integration.

    ``available`` means that the source ingredients required to derive a capability
    are present in the shared strategy context. It does not mean that the capability
    is already calculated or allowed to influence a live decision.
    """

    evidence = context.market_evidence
    frames = tuple(context.frames)
    fresh_candle_frames = tuple(
        frame for frame in frames if frame.recent_candles and not frame.is_stale
    )
    has_fresh_candles = bool(fresh_candle_frames)
    has_taker_flow = evidence is not None and bool(evidence.taker_flow)
    has_open_interest = evidence is not None and bool(evidence.open_interest)

    return HighValueEvidenceAudit(
        records=(
            EvidenceUsageRecord(
                capability=EvidenceCapability.AGGREGATE_TRADE_IMBALANCE,
                available=has_taker_flow,
                centrally_derived=has_taker_flow,
                freshness_guarded=has_taker_flow,
                source_labels=("taker_flow_history_proxy",) if has_taker_flow else (),
            ),
            EvidenceUsageRecord(
                capability=EvidenceCapability.PRICE_OPEN_INTEREST_RELATIONSHIP,
                available=has_open_interest and has_fresh_candles,
                centrally_derived=False,
                freshness_guarded=has_open_interest and has_fresh_candles,
                source_labels=("open_interest_history", "closed_candles")
                if has_open_interest and has_fresh_candles
                else (),
            ),
            EvidenceUsageRecord(
                capability=EvidenceCapability.BREAKOUT_ACCEPTANCE_DURATION,
                available=has_fresh_candles,
                centrally_derived=False,
                freshness_guarded=has_fresh_candles,
                source_labels=("closed_candles",) if has_fresh_candles else (),
            ),
            EvidenceUsageRecord(
                capability=EvidenceCapability.PULLBACK_VOLUME_DECAY,
                available=has_fresh_candles,
                centrally_derived=False,
                freshness_guarded=has_fresh_candles,
                source_labels=("closed_candle_volume",) if has_fresh_candles else (),
            ),
            EvidenceUsageRecord(
                capability=EvidenceCapability.SPREAD_DETERIORATION,
                available=False,
                centrally_derived=False,
                freshness_guarded=False,
            ),
            EvidenceUsageRecord(
                capability=EvidenceCapability.DEPTH_IMBALANCE,
                available=False,
                centrally_derived=False,
                freshness_guarded=False,
            ),
            EvidenceUsageRecord(
                capability=EvidenceCapability.LIQUIDATION_IMPULSE,
                available=False,
                centrally_derived=False,
                freshness_guarded=False,
            ),
        )
    )


def high_value_evidence_audit_payload(audit: HighValueEvidenceAudit) -> dict[str, Any]:
    return {
        "records": [
            {
                "capability": item.capability.value,
                "readiness": item.readiness.value,
                "available": item.available,
                "centrally_derived": item.centrally_derived,
                "freshness_guarded": item.freshness_guarded,
                "decision_bindings": list(item.decision_bindings),
                "source_labels": list(item.source_labels),
            }
            for item in audit.records
        ],
        "ready_capabilities": [item.value for item in audit.ready_capabilities],
        "incomplete_capabilities": [item.value for item in audit.incomplete_capabilities],
    }


__all__ = [
    "EvidenceCapability",
    "EvidenceReadiness",
    "EvidenceUsageRecord",
    "HighValueEvidenceAudit",
    "build_current_high_value_evidence_audit",
    "high_value_evidence_audit_payload",
]
