# Truthful reconciliation between evidence inventory and runtime derivation.

from __future__ import annotations

from dataclasses import replace

from apex.application.high_value_evidence_audit import (
    EvidenceCapability,
    EvidenceUsageRecord,
    HighValueEvidenceAudit,
    build_current_high_value_evidence_audit,
)
from apex.application.high_value_evidence_runtime import (
    HighValueEvidenceRuntimeSnapshot,
)
from apex.strategies import StrategyContext


def reconcile_high_value_evidence_audit(
    context: StrategyContext,
    runtime: HighValueEvidenceRuntimeSnapshot,
) -> HighValueEvidenceAudit:
    """Require actual runtime derivation before a capability is called available."""

    inventory = build_current_high_value_evidence_audit(context)
    records = tuple(_reconcile_record(record, runtime) for record in inventory.records)
    return HighValueEvidenceAudit(records=records)


def _reconcile_record(
    record: EvidenceUsageRecord,
    runtime: HighValueEvidenceRuntimeSnapshot,
) -> EvidenceUsageRecord:
    if record.capability is EvidenceCapability.AGGREGATE_TRADE_IMBALANCE:
        proxy = runtime.taker_flow_imbalance
        if proxy is None:
            return replace(
                record,
                available=False,
                centrally_derived=False,
                freshness_guarded=False,
                decision_bindings=(),
                source_labels=(),
            )
        return replace(
            record,
            available=True,
            centrally_derived=True,
            freshness_guarded=True,
            decision_bindings=(),
            source_labels=(proxy.source_label,),
        )

    if record.capability is EvidenceCapability.PRICE_OPEN_INTEREST_RELATIONSHIP:
        relationship = runtime.price_open_interest
        if relationship is None:
            return replace(
                record,
                available=False,
                centrally_derived=False,
                freshness_guarded=False,
                decision_bindings=(),
                source_labels=(),
            )
        return replace(
            record,
            available=True,
            centrally_derived=True,
            freshness_guarded=True,
            decision_bindings=(),
            source_labels=relationship.source_labels,
        )

    return record


__all__ = ["reconcile_high_value_evidence_audit"]
