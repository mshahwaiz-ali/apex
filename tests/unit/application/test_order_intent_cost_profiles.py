from __future__ import annotations

from dataclasses import dataclass

from apex.application.methodology_candidate_routing import (
    _candidate_execution_cost_profile,
)


@dataclass(frozen=True)
class _Candidate:
    metadata: dict[str, object]


def test_explicit_resting_order_uses_limit_profile() -> None:
    assert (
        _candidate_execution_cost_profile(_Candidate({"resting_order_authorized": True}))[0]
        == "limit"
    )


def test_explicit_limit_intent_uses_limit_profile() -> None:
    assert (
        _candidate_execution_cost_profile(_Candidate({"order_intent": "resting limit"}))[0]
        == "limit"
    )


def test_unknown_intent_remains_conservative_market() -> None:
    profile, reason = _candidate_execution_cost_profile(_Candidate({}))
    assert profile == "market"
    assert "conservative market" in reason
