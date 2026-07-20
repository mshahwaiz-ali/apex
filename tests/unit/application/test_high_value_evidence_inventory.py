from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from apex.application.high_value_evidence_audit import (
    EvidenceCapability,
    EvidenceReadiness,
    build_current_high_value_evidence_audit,
)


def _context(*, stale: bool = False, include_derivatives: bool = True) -> Any:
    frame = SimpleNamespace(
        recent_candles=(object(), object()),
        is_stale=stale,
    )
    evidence = SimpleNamespace(
        taker_flow=(object(),) if include_derivatives else (),
        open_interest=(object(),) if include_derivatives else (),
        as_of=datetime(2026, 7, 20, tzinfo=UTC),
    )
    return SimpleNamespace(frames=(frame,), market_evidence=evidence)


def _record_by_capability(audit: Any, capability: EvidenceCapability) -> Any:
    return next(item for item in audit.records if item.capability is capability)


def test_current_inventory_reports_sources_without_claiming_decision_bindings() -> None:
    audit = build_current_high_value_evidence_audit(cast(Any, _context()))

    taker = _record_by_capability(audit, EvidenceCapability.AGGREGATE_TRADE_IMBALANCE)
    price_oi = _record_by_capability(audit, EvidenceCapability.PRICE_OPEN_INTEREST_RELATIONSHIP)
    acceptance = _record_by_capability(audit, EvidenceCapability.BREAKOUT_ACCEPTANCE_DURATION)

    assert taker.readiness is EvidenceReadiness.AVAILABLE_UNUSED
    assert taker.source_labels == ("taker_flow_history_proxy",)
    assert price_oi.available is True
    assert price_oi.centrally_derived is False
    assert price_oi.decision_bindings == ()
    assert acceptance.available is True
    assert acceptance.decision_bindings == ()
    assert audit.ready_capabilities == ()


def test_stale_candles_block_candle_dependent_inventory_capabilities() -> None:
    audit = build_current_high_value_evidence_audit(cast(Any, _context(stale=True)))

    assert (
        _record_by_capability(audit, EvidenceCapability.PRICE_OPEN_INTEREST_RELATIONSHIP).available
        is False
    )
    assert (
        _record_by_capability(audit, EvidenceCapability.BREAKOUT_ACCEPTANCE_DURATION).available
        is False
    )
    assert _record_by_capability(audit, EvidenceCapability.PULLBACK_VOLUME_DECAY).available is False


def test_inventory_keeps_unsupported_live_series_unavailable() -> None:
    audit = build_current_high_value_evidence_audit(cast(Any, _context(include_derivatives=False)))

    assert (
        _record_by_capability(audit, EvidenceCapability.SPREAD_DETERIORATION).readiness
        is EvidenceReadiness.UNAVAILABLE
    )
    assert (
        _record_by_capability(audit, EvidenceCapability.DEPTH_IMBALANCE).readiness
        is EvidenceReadiness.UNAVAILABLE
    )
    assert (
        _record_by_capability(audit, EvidenceCapability.LIQUIDATION_IMPULSE).readiness
        is EvidenceReadiness.UNAVAILABLE
    )
