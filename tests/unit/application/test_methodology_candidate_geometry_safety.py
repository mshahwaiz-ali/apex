from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from apex.application.methodology_candidate_geometry_safety import (
    audit_candidate_geometry_safety,
    candidate_geometry_safety_audit_payload,
)
from apex.application.methodology_geometry_safety import GeometrySafetyState
from apex.application.opportunity_portfolio import OpportunityLane
from apex.strategies.contracts import TradeCandidate, TradeDirection


@dataclass(frozen=True)
class _Entry:
    lower: float = 99.5
    upper: float = 100.5
    preferred: float = 100.0


@dataclass(frozen=True)
class _Invalidation:
    price: float = 98.5


@dataclass(frozen=True)
class _Target:
    price: float
    label: str = "TP1"


@dataclass(frozen=True)
class _Targets:
    levels: tuple[_Target, ...]


@dataclass(frozen=True)
class _Quality:
    target_space_quality: float = 0.8


@dataclass(frozen=True)
class _Candidate:
    symbol: str
    direction: TradeDirection
    decision_time: datetime
    entry: _Entry
    invalidation: _Invalidation
    targets: _Targets
    quality: _Quality
    metadata: dict[str, Any]


def _candidate(metadata: dict[str, Any]) -> TradeCandidate:
    return cast(
        TradeCandidate,
        _Candidate(
            symbol="TESTUSDT",
            direction=TradeDirection.LONG,
            decision_time=datetime(2026, 7, 21, tzinfo=UTC),
            entry=_Entry(),
            invalidation=_Invalidation(),
            targets=_Targets((_Target(103.0),)),
            quality=_Quality(),
            metadata=metadata,
        ),
    )


def test_shadow_audit_is_unavailable_without_explicit_stop_and_costs() -> None:
    audit = audit_candidate_geometry_safety(
        _candidate({}),
        candidate_id="momentum_breakout:long:0",
        lane=OpportunityLane.CMP_SCALP,
    )

    assert audit.assessment is None
    assert audit.missing_measurements == ("executable_stop", "expected_cost_pct")
    payload = candidate_geometry_safety_audit_payload(audit)
    assert payload["available"] is False
    assert payload["shadow_only"] is True


def test_shadow_audit_uses_explicit_execution_buffer_and_cost_components() -> None:
    audit = audit_candidate_geometry_safety(
        _candidate(
            {
                "execution_buffer": 0.5,
                "entry_fee_pct": 0.02,
                "exit_fee_pct": 0.02,
                "entry_slippage_pct": 0.03,
                "exit_slippage_pct": 0.03,
            }
        ),
        candidate_id="momentum_breakout:long:0",
        lane=OpportunityLane.CMP_SCALP,
    )

    assert audit.assessment is not None
    assert audit.assessment.state is GeometrySafetyState.PASS
    assert audit.assessment.diagnostics.executable_stop == 98.0
    assert audit.assessment.diagnostics.expected_cost_pct == 0.1
    payload = candidate_geometry_safety_audit_payload(audit)
    assert payload["available"] is True
    assert payload["state"] == "pass"
    assert payload["diagnostics"] is not None


def test_shadow_audit_never_treats_missing_cost_components_as_zero() -> None:
    audit = audit_candidate_geometry_safety(
        _candidate({"execution_buffer": 0.5, "entry_fee_pct": 0.02}),
        candidate_id="momentum_breakout:long:0",
        lane=OpportunityLane.CMP_SCALP,
    )

    assert audit.assessment is None
    assert audit.missing_measurements == ("expected_cost_pct",)
