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


def test_zero_trade_diagnostics_prioritize_best_ranked_rejection_reason() -> None:
    primary_alignment = SimpleNamespace(
        reasons=("Market environment is explicitly untradeable for new candidates",)
    )
    primary = SimpleNamespace(
        scored=SimpleNamespace(environment_route_alignment=primary_alignment),
        reasons=("score 0.00 is below aggressive floor 52.00",),
        outcome=SimpleNamespace(value="rejected_below_threshold"),
    )
    duplicate = SimpleNamespace(
        scored=SimpleNamespace(environment_route_alignment=None),
        reasons=("duplicate thesis supports primary candidate candidate-1",),
        outcome=SimpleNamespace(value="rejected_duplicate"),
    )
    analysis = SimpleNamespace(
        candidates=(
            SimpleNamespace(strategy=StrategyType.TREND_PULLBACK),
            SimpleNamespace(strategy=StrategyType.TREND_PULLBACK),
        ),
        candidate_actionability=(),
        strategy_diagnostics={},
    )
    selection = SimpleNamespace(
        selected_candidate=None,
        no_trade_reason="candidate selection produced no setup",
        ranked_candidates=(primary, duplicate),
        rejected_candidates=(primary, duplicate),
        all_scored_candidates=(primary.scored, duplicate.scored),
        metadata={},
    )
    assessment = SimpleNamespace(developing_setup=None)
    methodology_routing = SimpleNamespace(
        mode=SimpleNamespace(value="enforce"),
        input_candidate_count=2,
        suppressed_candidate_count=0,
        suppressed_strategies=(),
        reason_codes=("METHODOLOGY_CANDIDATE_ROUTING_NO_CHANGE",),
    )

    payload = _zero_trade_diagnostics(
        strategy_analysis=analysis,
        eligible_routed=analysis,
        selection=selection,
        assessment=assessment,
        methodology_routing=methodology_routing,
    )

    assert payload["top_rejected_reasons"][0]["reason"] == (
        "Market environment is explicitly untradeable for new candidates"
    )
