from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from apex.application.analysis import ScanResult
from apex.application.paper_pipeline_diagnostics import (
    build_futures_pipeline_diagnostics,
)
from apex.domain import MarketCategory


def _analysis(scanner_type: MarketCategory, candidate_count: int) -> SimpleNamespace:
    return SimpleNamespace(
        symbol="BTC/USDT",
        scanner_type=scanner_type,
        candidate_count=candidate_count,
        strategy_routing={
            "decision_regime": "reversal_transition",
            "higher_timeframe_breakout": True,
            "near_miss_state_counts": {"wait_for_retest": 1},
            "phase4_strategy_diagnostics": {
                "breakout_continuation": {
                    "candidate_count": candidate_count,
                    "near_miss_state": "wait_for_retest",
                }
            },
            "routed_eligible_strategies": ["breakout_continuation"],
            "skipped_strategies": {"range_reversal": "route disabled"},
        },
    )


def test_aggregates_phase4_diagnostics_by_symbol_and_scanner() -> None:
    scan = cast(
        ScanResult,
        SimpleNamespace(
            analyses=(
                _analysis(MarketCategory.NORMAL_MARKET, 0),
                _analysis(MarketCategory.GAINER, 1),
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
    assert normal["phase4_strategy_diagnostics"]["breakout_continuation"] == {
        "candidate_count": 0,
        "near_miss_state": "wait_for_retest",
    }
