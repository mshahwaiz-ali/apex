from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from apex.application.discovery_analysis import _high_value_evidence_diagnostics


def test_high_value_evidence_diagnostics_are_observational_and_deterministic() -> None:
    context = SimpleNamespace(
        frames=(SimpleNamespace(recent_candles=(object(),), is_stale=False),),
        market_evidence=SimpleNamespace(taker_flow=(object(),), open_interest=(object(),)),
    )

    payload = _high_value_evidence_diagnostics(cast(Any, context))

    assert payload["ready_capabilities"] == []
    assert payload["incomplete_capabilities"] == [
        "aggregate_trade_imbalance",
        "price_open_interest_relationship",
        "breakout_acceptance_duration",
        "pullback_volume_decay",
        "spread_deterioration",
        "depth_imbalance",
        "liquidation_impulse",
    ]
    records = {item["capability"]: item for item in payload["records"]}
    assert records["aggregate_trade_imbalance"] == {
        "capability": "aggregate_trade_imbalance",
        "readiness": "available_unused",
        "available": True,
        "centrally_derived": True,
        "freshness_guarded": True,
        "decision_bindings": [],
        "source_labels": ["taker_flow_history_proxy"],
    }
    assert records["spread_deterioration"]["readiness"] == "unavailable"


def test_high_value_evidence_diagnostics_do_not_invent_missing_sources() -> None:
    context = SimpleNamespace(
        frames=(SimpleNamespace(recent_candles=(), is_stale=True),),
        market_evidence=None,
    )

    payload = _high_value_evidence_diagnostics(cast(Any, context))

    assert payload["ready_capabilities"] == []
    assert all(item["readiness"] == "unavailable" for item in payload["records"])
    assert all(item["decision_bindings"] == [] for item in payload["records"])
