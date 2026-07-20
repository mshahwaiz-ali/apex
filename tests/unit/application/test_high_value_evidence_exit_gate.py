from __future__ import annotations

from apex.application.high_value_evidence_audit import (
    EvidenceCapability,
    EvidenceUsageRecord,
    HighValueEvidenceAudit,
)
from apex.application.high_value_evidence_exit_gate import (
    evaluate_high_value_evidence_exit_gate,
    high_value_evidence_exit_gate_payload,
)


def _record(
    capability: EvidenceCapability,
    *,
    available: bool,
    derived: bool = False,
    guarded: bool = False,
    bindings: tuple[str, ...] = (),
) -> EvidenceUsageRecord:
    return EvidenceUsageRecord(
        capability=capability,
        available=available,
        centrally_derived=derived,
        freshness_guarded=guarded,
        decision_bindings=bindings,
        source_labels=(f"{capability.value}_source",) if available else (),
    )


def test_exit_gate_reports_available_but_unused_priority_features() -> None:
    audit = HighValueEvidenceAudit(
        records=(
            _record(
                EvidenceCapability.AGGREGATE_TRADE_IMBALANCE,
                available=True,
                derived=True,
                guarded=True,
            ),
            _record(
                EvidenceCapability.PRICE_OPEN_INTEREST_RELATIONSHIP,
                available=True,
                derived=True,
                guarded=True,
            ),
            _record(EvidenceCapability.BREAKOUT_ACCEPTANCE_DURATION, available=False),
            _record(EvidenceCapability.PULLBACK_VOLUME_DECAY, available=False),
        )
    )

    gate = evaluate_high_value_evidence_exit_gate(audit)

    assert gate.complete is False
    assert gate.available_capabilities == (
        EvidenceCapability.AGGREGATE_TRADE_IMBALANCE,
        EvidenceCapability.PRICE_OPEN_INTEREST_RELATIONSHIP,
    )
    assert gate.decision_bound_capabilities == ()
    assert gate.blockers == (
        "aggregate_trade_imbalance:not_decision_bound",
        "breakout_acceptance_duration:unavailable",
        "price_open_interest_relationship:not_decision_bound",
        "pullback_volume_decay:unavailable",
    )


def test_exit_gate_completes_only_when_all_priority_features_are_ready() -> None:
    capabilities = (
        EvidenceCapability.AGGREGATE_TRADE_IMBALANCE,
        EvidenceCapability.PRICE_OPEN_INTEREST_RELATIONSHIP,
        EvidenceCapability.BREAKOUT_ACCEPTANCE_DURATION,
        EvidenceCapability.PULLBACK_VOLUME_DECAY,
    )
    audit = HighValueEvidenceAudit(
        records=tuple(
            _record(
                capability,
                available=True,
                derived=True,
                guarded=True,
                bindings=(f"strategy:{capability.value}",),
            )
            for capability in capabilities
        )
    )

    gate = evaluate_high_value_evidence_exit_gate(audit)
    payload = high_value_evidence_exit_gate_payload(gate)

    assert gate.complete is True
    assert gate.blockers == ()
    assert payload["complete"] is True
    assert payload["decision_bound_capabilities"] == [
        capability.value for capability in capabilities
    ]
