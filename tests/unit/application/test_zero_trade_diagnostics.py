"""Tests for strict zero-trade diagnostics."""

from types import SimpleNamespace

from apex.application.discovery_analysis import _zero_trade_diagnostics
from apex.strategies.entry_status import EntryStatus
from apex.strategies.stage3_diagnostics import StrategyDiagnostic, StrategyRejectionCode
from apex.strategies.strategy_types import StrategyType


def test_zero_trade_diagnostics_preserve_strict_filter_policy() -> None:
    diagnostic = StrategyDiagnostic(
        strategy=StrategyType.TREND_PULLBACK,
        candidate_count=0,
        rejection_codes=(StrategyRejectionCode.MISSING_ENTRY_REFERENCES,),
        reasons=("no structural, EMA, or VWAP pullback reference exists",),
        near_miss_state=EntryStatus.WATCH_NEAR_ENTRY,
    )
    analysis = SimpleNamespace(
        candidates=(),
        candidate_actionability=(),
        strategy_diagnostics={StrategyType.TREND_PULLBACK: diagnostic},
    )
    selection = SimpleNamespace(
        selected_candidate=None,
        no_trade_reason="candidate selection produced no setup",
        ranked_candidates=(),
        rejected_candidates=(),
    )
    assessment = SimpleNamespace(developing_setup=None)
    methodology_routing = SimpleNamespace(
        mode=SimpleNamespace(value="shadow"),
        suppressed_candidate_count=0,
        suppressed_strategies=(),
        reason_codes=("METHODOLOGY_CANDIDATE_ROUTING_SHADOW",),
    )

    payload = _zero_trade_diagnostics(
        strategy_analysis=analysis,
        eligible_routed=analysis,
        selection=selection,
        assessment=assessment,
        methodology_routing=methodology_routing,
    )

    assert payload["decision"] == "NO_TRADE"
    assert "do not loosen entry filters" in payload["execution_filter_policy"]
    assert payload["strategy_rejection_code_distribution"] == {"missing_entry_references": 1}
    assert payload["strategy_diagnostics"]["trend_pullback"]["near_miss_state"] == (
        "WATCH_NEAR_ENTRY"
    )
