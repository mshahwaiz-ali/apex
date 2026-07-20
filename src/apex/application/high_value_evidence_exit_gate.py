"""Deterministic Batch 9 evidence exit-gate reporting."""

from __future__ import annotations

from dataclasses import dataclass

from apex.application.high_value_evidence_audit import (
    EvidenceCapability,
    EvidenceReadiness,
    HighValueEvidenceAudit,
)

_PRIORITY_CAPABILITIES = (
    EvidenceCapability.AGGREGATE_TRADE_IMBALANCE,
    EvidenceCapability.PRICE_OPEN_INTEREST_RELATIONSHIP,
    EvidenceCapability.BREAKOUT_ACCEPTANCE_DURATION,
    EvidenceCapability.PULLBACK_VOLUME_DECAY,
)


@dataclass(frozen=True, slots=True)
class HighValueEvidenceExitGate:
    priority_capabilities: tuple[EvidenceCapability, ...]
    available_capabilities: tuple[EvidenceCapability, ...]
    decision_bound_capabilities: tuple[EvidenceCapability, ...]
    blockers: tuple[str, ...]
    complete: bool

    def __post_init__(self) -> None:
        if len(set(self.priority_capabilities)) != len(self.priority_capabilities):
            raise ValueError("priority capabilities must be unique")
        if len(set(self.available_capabilities)) != len(self.available_capabilities):
            raise ValueError("available capabilities must be unique")
        if len(set(self.decision_bound_capabilities)) != len(self.decision_bound_capabilities):
            raise ValueError("decision-bound capabilities must be unique")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("exit-gate blockers must be unique")
        expected = not self.blockers and set(self.priority_capabilities).issubset(
            self.decision_bound_capabilities
        )
        if self.complete is not expected:
            raise ValueError("exit-gate completion must match blockers and bindings")


def evaluate_high_value_evidence_exit_gate(
    audit: HighValueEvidenceAudit,
) -> HighValueEvidenceExitGate:
    records = {record.capability: record for record in audit.records}
    available: list[EvidenceCapability] = []
    decision_bound: list[EvidenceCapability] = []
    blockers: list[str] = []

    for capability in _PRIORITY_CAPABILITIES:
        record = records.get(capability)
        if record is None:
            blockers.append(f"{capability.value}:missing_audit_record")
            continue

        if record.readiness is not EvidenceReadiness.UNAVAILABLE:
            available.append(capability)

        if record.readiness is EvidenceReadiness.READY:
            decision_bound.append(capability)
            continue

        if record.readiness is EvidenceReadiness.UNAVAILABLE:
            blockers.append(f"{capability.value}:unavailable")
        elif record.readiness is EvidenceReadiness.AVAILABLE_UNUSED:
            blockers.append(f"{capability.value}:not_decision_bound")
        elif record.readiness is EvidenceReadiness.DECISION_BOUND_UNGUARDED:
            blockers.append(f"{capability.value}:missing_freshness_or_central_derivation")

    blockers_tuple = tuple(sorted(blockers))
    return HighValueEvidenceExitGate(
        priority_capabilities=_PRIORITY_CAPABILITIES,
        available_capabilities=tuple(available),
        decision_bound_capabilities=tuple(decision_bound),
        blockers=blockers_tuple,
        complete=not blockers_tuple and set(_PRIORITY_CAPABILITIES).issubset(decision_bound),
    )


def high_value_evidence_exit_gate_payload(
    gate: HighValueEvidenceExitGate,
) -> dict[str, object]:
    return {
        "complete": gate.complete,
        "priority_capabilities": [capability.value for capability in gate.priority_capabilities],
        "available_capabilities": [capability.value for capability in gate.available_capabilities],
        "decision_bound_capabilities": [
            capability.value for capability in gate.decision_bound_capabilities
        ],
        "blockers": list(gate.blockers),
        "policy": (
            "priority evidence must be centrally derived, freshness guarded, "
            "and explicitly bound to a strategy or state decision"
        ),
    }


__all__ = [
    "HighValueEvidenceExitGate",
    "evaluate_high_value_evidence_exit_gate",
    "high_value_evidence_exit_gate_payload",
]
