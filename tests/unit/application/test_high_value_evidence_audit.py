from __future__ import annotations

import pytest

from apex.application.high_value_evidence_audit import (
    EvidenceCapability,
    EvidenceReadiness,
    EvidenceUsageRecord,
    HighValueEvidenceAudit,
    high_value_evidence_audit_payload,
)


def test_evidence_readiness_requires_availability_usage_and_guards() -> None:
    unavailable = EvidenceUsageRecord(
        capability=EvidenceCapability.LIQUIDATION_IMPULSE,
        available=False,
        centrally_derived=False,
        freshness_guarded=False,
    )
    unused = EvidenceUsageRecord(
        capability=EvidenceCapability.SPREAD_DETERIORATION,
        available=True,
        centrally_derived=True,
        freshness_guarded=True,
        source_labels=("best_bid_ask",),
    )
    unguarded = EvidenceUsageRecord(
        capability=EvidenceCapability.PULLBACK_VOLUME_DECAY,
        available=True,
        centrally_derived=True,
        freshness_guarded=False,
        decision_bindings=("first_pullback.execution_quality",),
        source_labels=("klines",),
    )
    ready = EvidenceUsageRecord(
        capability=EvidenceCapability.BREAKOUT_ACCEPTANCE_DURATION,
        available=True,
        centrally_derived=True,
        freshness_guarded=True,
        decision_bindings=("momentum_breakout.activation",),
        source_labels=("closed_1m_candles",),
    )

    assert unavailable.readiness is EvidenceReadiness.UNAVAILABLE
    assert unused.readiness is EvidenceReadiness.AVAILABLE_UNUSED
    assert unguarded.readiness is EvidenceReadiness.DECISION_BOUND_UNGUARDED
    assert ready.readiness is EvidenceReadiness.READY


def test_audit_payload_is_deterministic_and_preserves_bindings() -> None:
    audit = HighValueEvidenceAudit(
        records=(
            EvidenceUsageRecord(
                capability=EvidenceCapability.AGGREGATE_TRADE_IMBALANCE,
                available=True,
                centrally_derived=True,
                freshness_guarded=True,
                decision_bindings=("micro_confirmation.activation",),
                source_labels=("aggregate_trades",),
            ),
            EvidenceUsageRecord(
                capability=EvidenceCapability.DEPTH_IMBALANCE,
                available=False,
                centrally_derived=False,
                freshness_guarded=False,
            ),
        )
    )

    assert high_value_evidence_audit_payload(audit) == {
        "records": [
            {
                "capability": "aggregate_trade_imbalance",
                "readiness": "ready",
                "available": True,
                "centrally_derived": True,
                "freshness_guarded": True,
                "decision_bindings": ["micro_confirmation.activation"],
                "source_labels": ["aggregate_trades"],
            },
            {
                "capability": "depth_imbalance",
                "readiness": "unavailable",
                "available": False,
                "centrally_derived": False,
                "freshness_guarded": False,
                "decision_bindings": [],
                "source_labels": [],
            },
        ],
        "ready_capabilities": ["aggregate_trade_imbalance"],
        "incomplete_capabilities": ["depth_imbalance"],
    }


def test_audit_rejects_duplicate_capabilities() -> None:
    record = EvidenceUsageRecord(
        capability=EvidenceCapability.PRICE_OPEN_INTEREST_RELATIONSHIP,
        available=False,
        centrally_derived=False,
        freshness_guarded=False,
    )

    with pytest.raises(ValueError, match="capabilities must be unique"):
        HighValueEvidenceAudit(records=(record, record))


def test_unavailable_evidence_cannot_claim_wiring() -> None:
    with pytest.raises(ValueError, match="cannot claim wiring"):
        EvidenceUsageRecord(
            capability=EvidenceCapability.DEPTH_IMBALANCE,
            available=False,
            centrally_derived=False,
            freshness_guarded=True,
        )
