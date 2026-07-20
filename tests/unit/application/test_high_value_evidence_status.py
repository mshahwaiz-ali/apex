from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from apex.application.high_value_evidence_audit import (
    EvidenceCapability,
    EvidenceReadiness,
)
from apex.application.high_value_evidence_features import (
    ChangeDirection,
    PriceOpenInterestRelationship,
    PriceOpenInterestState,
    TakerFlowImbalanceProxy,
)
from apex.application.high_value_evidence_runtime import (
    HighValueEvidenceRuntimeSnapshot,
)
from apex.application.high_value_evidence_status import (
    reconcile_high_value_evidence_audit,
)

NOW = datetime(2026, 7, 20, 12, 30, tzinfo=UTC)


def _context() -> Any:
    return SimpleNamespace(
        frames=(SimpleNamespace(recent_candles=(object(), object()), is_stale=False),),
        market_evidence=SimpleNamespace(
            taker_flow=(object(),),
            open_interest=(object(), object()),
        ),
    )


def _record(audit: Any, capability: EvidenceCapability) -> Any:
    return next(item for item in audit.records if item.capability is capability)


def test_reconciliation_downgrades_inventory_when_runtime_derivation_failed() -> None:
    runtime = HighValueEvidenceRuntimeSnapshot(
        taker_flow_imbalance=None,
        price_open_interest=None,
        unavailable_reasons=(
            ("price_open_interest_relationship", "stale_or_unsynchronized_price_open_interest"),
            ("taker_flow_imbalance_proxy", "taker_flow_empty_or_unusable"),
        ),
    )

    audit = reconcile_high_value_evidence_audit(cast(Any, _context()), runtime)

    taker = _record(audit, EvidenceCapability.AGGREGATE_TRADE_IMBALANCE)
    price_oi = _record(audit, EvidenceCapability.PRICE_OPEN_INTEREST_RELATIONSHIP)
    assert taker.readiness is EvidenceReadiness.UNAVAILABLE
    assert price_oi.readiness is EvidenceReadiness.UNAVAILABLE
    assert taker.source_labels == ()
    assert price_oi.source_labels == ()
    assert audit.ready_capabilities == ()


def test_reconciliation_marks_derived_features_available_but_not_decision_bound() -> None:
    runtime = HighValueEvidenceRuntimeSnapshot(
        taker_flow_imbalance=TakerFlowImbalanceProxy(
            buy_volume=75.0,
            sell_volume=25.0,
            imbalance=0.5,
            sample_count=1,
            latest_captured_at=NOW,
        ),
        price_open_interest=PriceOpenInterestRelationship(
            price_change_pct=2.0,
            open_interest_change_pct=5.0,
            price_direction=ChangeDirection.RISING,
            open_interest_direction=ChangeDirection.RISING,
            state=PriceOpenInterestState.LONG_BUILDUP,
            start_at=datetime(2026, 7, 20, 12, 20, tzinfo=UTC),
            end_at=NOW,
            maximum_alignment_skew_seconds=10.0,
        ),
    )

    audit = reconcile_high_value_evidence_audit(cast(Any, _context()), runtime)

    taker = _record(audit, EvidenceCapability.AGGREGATE_TRADE_IMBALANCE)
    price_oi = _record(audit, EvidenceCapability.PRICE_OPEN_INTEREST_RELATIONSHIP)
    assert taker.readiness is EvidenceReadiness.AVAILABLE_UNUSED
    assert price_oi.readiness is EvidenceReadiness.AVAILABLE_UNUSED
    assert taker.centrally_derived is True
    assert price_oi.centrally_derived is True
    assert taker.freshness_guarded is True
    assert price_oi.freshness_guarded is True
    assert taker.decision_bindings == ()
    assert price_oi.decision_bindings == ()
    assert audit.ready_capabilities == ()
