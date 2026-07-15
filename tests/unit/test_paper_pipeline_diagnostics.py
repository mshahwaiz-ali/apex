from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from apex.application.analysis import ScanResult, SymbolAnalysis
from apex.application.paper_pipeline_diagnostics import (
    build_futures_pipeline_diagnostics,
    build_phase4_diagnostic_summary,
)
from apex.domain import MarketCategory


def _analysis(
    scanner_type: MarketCategory,
    *,
    candidate_count: int,
    regime: str = "uncertain",
    higher_timeframe_breakout: bool = True,
    routing: dict[str, object] | None = None,
) -> SymbolAnalysis:
    default_routing: dict[str, object] = {
        "decision_regime": regime,
        "higher_timeframe_breakout": higher_timeframe_breakout,
        "near_miss_state_counts": {"wait_for_retest": 1},
        "phase4_strategy_diagnostics": {
            "breakout_continuation": {
                "candidate_count": candidate_count,
                "rejection_codes": (
                    [] if candidate_count else ["missing_entry_references"]
                ),
                "near_miss_state": (
                    "ready_now" if candidate_count else "wait_for_retest"
                ),
            },
            "range_reversal": {
                "candidate_count": 0,
                "rejection_codes": ["regime_ineligible"],
                "near_miss_state": "no_trade",
            },
        },
        "routed_eligible_strategies": ["breakout_continuation"],
        "skipped_strategies": {"range_reversal": "route disabled"},
    }
    return cast(
        SymbolAnalysis,
        SimpleNamespace(
            symbol="BTC/USDT",
            scanner_type=scanner_type,
            candidate_count=candidate_count,
            strategy_routing=default_routing if routing is None else routing,
        ),
    )


def test_aggregates_phase4_diagnostics_by_symbol_and_scanner() -> None:
    scan = cast(
        ScanResult,
        SimpleNamespace(
            analyses=(
                _analysis(MarketCategory.NORMAL_MARKET, candidate_count=0),
                _analysis(MarketCategory.GAINER, candidate_count=1),
            ),
            failures={"ETH/USDT": "provider timeout"},
        ),
    )

    diagnostics = build_futures_pipeline_diagnostics(scan)

    assert diagnostics["scan_analysis_count"] == 2
    assert diagnostics["scanner_failure_count"] == 1
    assert diagnostics["scanner_failures"] == {"ETH/USDT": "provider timeout"}
    assert set(diagnostics["phase4_analyses"]) == {
        "BTC/USDT:NORMAL_MARKET",
        "BTC/USDT:GAINER",
    }
    normal = diagnostics["phase4_analyses"]["BTC/USDT:NORMAL_MARKET"]
    gainer = diagnostics["phase4_analyses"]["BTC/USDT:GAINER"]
    assert normal["candidate_count"] == 0
    assert gainer["candidate_count"] == 1
    assert normal["higher_timeframe_breakout"] is True
    assert normal["near_miss_state_counts"] == {"wait_for_retest": 1}


def test_run_summary_counts_rejections_candidates_and_strategy_states() -> None:
    summary = build_phase4_diagnostic_summary(
        (
            _analysis(MarketCategory.NORMAL_MARKET, candidate_count=0),
            _analysis(MarketCategory.GAINER, candidate_count=1),
        )
    ).to_payload()

    assert summary["rejection_code_counts"] == {
        "missing_entry_references": 1,
        "regime_ineligible": 2,
    }
    assert summary["rejection_counts_by_strategy"] == {
        "breakout_continuation": 1,
        "range_reversal": 2,
    }
    assert summary["rejection_counts_by_scanner_category"] == {
        "GAINER": 1,
        "NORMAL_MARKET": 2,
    }
    assert summary["rejection_counts_by_decision_regime"] == {"uncertain": 3}
    assert summary["rejection_counts_by_near_miss_state"] == {
        "no_trade": 2,
        "wait_for_retest": 1,
    }
    assert summary["candidate_counts_by_strategy"] == {
        "breakout_continuation": 1,
        "range_reversal": 0,
    }
    assert summary["strategy_totals"] == {
        "evaluated": 4,
        "eligible": 2,
        "skipped": 2,
        "producing_candidates": 1,
        "producing_zero_candidates": 3,
    }


def test_run_summary_tracks_higher_timeframe_breakout_fallback() -> None:
    summary = build_phase4_diagnostic_summary(
        (
            _analysis(MarketCategory.NORMAL_MARKET, candidate_count=0),
            _analysis(MarketCategory.GAINER, candidate_count=1),
            _analysis(
                MarketCategory.NORMAL_MARKET,
                candidate_count=1,
                regime="strong_uptrend",
                higher_timeframe_breakout=False,
            ),
        )
    ).to_payload()

    assert summary["higher_timeframe_breakout_fallback"] == {
        "detected": 2,
        "eligible_because_of_fallback": 2,
        "raw_candidate_produced": 1,
        "no_candidate_despite_fallback": 1,
    }


def test_partial_or_absent_routing_diagnostics_are_not_fabricated() -> None:
    summary = build_phase4_diagnostic_summary(
        (
            _analysis(
                MarketCategory.NORMAL_MARKET,
                candidate_count=0,
                routing={},
            ),
            _analysis(
                MarketCategory.GAINER,
                candidate_count=0,
                routing={
                    "decision_regime": "compression",
                    "phase4_strategy_diagnostics": None,
                    "routed_eligible_strategies": "breakout_continuation",
                    "skipped_strategies": None,
                },
            ),
        )
    ).to_payload()

    assert summary["rejection_code_counts"] == {}
    assert summary["candidate_counts_by_strategy"] == {}
    assert summary["strategy_totals"] == {
        "evaluated": 0,
        "eligible": 0,
        "skipped": 0,
        "producing_candidates": 0,
        "producing_zero_candidates": 0,
    }
    assert summary["higher_timeframe_breakout_fallback"] == {
        "detected": 0,
        "eligible_because_of_fallback": 0,
        "raw_candidate_produced": 0,
        "no_candidate_despite_fallback": 0,
    }


def test_serialized_summary_order_is_deterministic() -> None:
    routing = {
        "decision_regime": "uncertain",
        "higher_timeframe_breakout": False,
        "phase4_strategy_diagnostics": {
            "z_strategy": {
                "candidate_count": 0,
                "rejection_codes": ["z_code"],
                "near_miss_state": "watch",
            },
            "a_strategy": {
                "candidate_count": 0,
                "rejection_codes": ["a_code"],
                "near_miss_state": "no_trade",
            },
        },
        "routed_eligible_strategies": [],
        "skipped_strategies": {},
    }

    payload = build_phase4_diagnostic_summary(
        (
            _analysis(
                MarketCategory.NORMAL_MARKET,
                candidate_count=0,
                routing=routing,
            ),
        )
    ).to_payload()

    assert list(payload["rejection_code_counts"]) == ["a_code", "z_code"]
    assert list(payload["candidate_counts_by_strategy"]) == [
        "a_strategy",
        "z_strategy",
    ]
