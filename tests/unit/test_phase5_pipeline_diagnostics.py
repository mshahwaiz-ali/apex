from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from apex.application.analysis import ScanResult, SymbolAnalysis
from apex.application.paper_pipeline_diagnostics import build_futures_pipeline_diagnostics
from apex.application.phase5_pipeline_diagnostics import (
    build_phase5_diagnostic_summary,
    phase5_analysis_payload,
)
from apex.domain import MarketCategory


def _analysis(
    scanner_type: MarketCategory,
    *,
    selected: bool,
    selected_candidate_id: str | None = None,
    no_trade_reason: str | None = None,
    candidates: list[dict[str, object]] | None = None,
) -> SymbolAnalysis:
    candidate_payloads = candidates or []
    return cast(
        SymbolAnalysis,
        SimpleNamespace(
            symbol="BTC/USDT",
            scanner_type=scanner_type,
            candidate_count=len(candidate_payloads),
            strategy_routing={},
            phase5_diagnostics={
                "candidate_count": len(candidate_payloads),
                "ranked_count": len(candidate_payloads),
                "rejected_count": sum(
                    str(item["outcome"]).startswith("rejected")
                    for item in candidate_payloads
                ),
                "selected": selected,
                "selected_candidate_id": selected_candidate_id,
                "no_trade_reason": no_trade_reason,
                "candidates": candidate_payloads,
            },
        ),
    )


def test_phase5_summary_aggregates_funnels_outcomes_scores_and_selection() -> None:
    analyses = (
        _analysis(
            MarketCategory.NORMAL_MARKET,
            selected=True,
            selected_candidate_id="normal-1",
            candidates=[
                {
                    "candidate_id": "normal-1",
                    "strategy": "trend_pullback",
                    "direction": "long",
                    "outcome": "accepted",
                    "final_score": 82.0,
                    "reasons": [],
                },
                {
                    "candidate_id": "normal-2",
                    "strategy": "breakout_continuation",
                    "direction": "long",
                    "outcome": "rejected_below_score_threshold",
                    "final_score": 52.0,
                    "reasons": ["below threshold"],
                },
            ],
        ),
        _analysis(
            MarketCategory.GAINER,
            selected=False,
            no_trade_reason="opposing candidates remain unresolved inside the conflict margin",
            candidates=[
                {
                    "candidate_id": "gainer-1",
                    "strategy": "momentum_gainer_continuation",
                    "direction": "short",
                    "outcome": "downgraded",
                    "final_score": 68.0,
                    "reasons": ["mixed direction"],
                }
            ],
        ),
    )

    payload = build_phase5_diagnostic_summary(analyses).to_payload()

    assert payload["analysis_funnel"] == {
        "observed": 2,
        "with_candidates": 2,
        "selected": 1,
        "no_trade": 1,
    }
    assert payload["candidate_funnel"] == {
        "scored": 3,
        "ranked": 3,
        "accepted": 1,
        "rejected": 1,
        "downgraded": 1,
    }
    assert payload["outcome_counts"] == {
        "accepted": 1,
        "downgraded": 1,
        "rejected_below_score_threshold": 1,
    }
    assert payload["selected_counts_by_strategy"] == {"trend_pullback": 1}
    assert payload["selected_counts_by_direction"] == {"long": 1}
    assert payload["score_band_counts"] == {
        "85_100_exceptional": 0,
        "75_84_strong": 1,
        "65_74_valid_aggressive": 1,
        "55_64_weak_experimental": 0,
        "below_55_rejected": 1,
    }
    assert payload["average_final_score_by_strategy"] == {
        "breakout_continuation": 52.0,
        "momentum_gainer_continuation": 68.0,
        "trend_pullback": 82.0,
    }


def test_phase5_summary_does_not_infer_missing_selection_identity() -> None:
    payload = build_phase5_diagnostic_summary(
        (
            _analysis(
                MarketCategory.NORMAL_MARKET,
                selected=True,
                candidates=[
                    {
                        "candidate_id": "candidate-1",
                        "strategy": "trend_pullback",
                        "direction": "long",
                        "outcome": "accepted",
                        "final_score": 80.0,
                        "reasons": [],
                    }
                ],
            ),
        )
    ).to_payload()

    assert payload["analysis_funnel"]["selected"] == 1
    assert payload["selected_counts_by_strategy"] == {}
    assert payload["selected_counts_by_direction"] == {}


def test_phase5_analysis_payload_handles_absent_diagnostics() -> None:
    analysis = _analysis(MarketCategory.GAINER, selected=False)
    analysis.phase5_diagnostics.clear()  # type: ignore[union-attr]

    payload = phase5_analysis_payload(analysis)

    assert payload["candidate_count"] == 0
    assert payload["ranked_count"] == 0
    assert payload["selected"] is False
    assert payload["outcome_counts"] == {}
    assert payload["candidates"] == []


def test_pipeline_payload_preserves_distinct_scanner_paths_and_phase5_summary() -> None:
    scan = cast(
        ScanResult,
        SimpleNamespace(
            analyses=(
                _analysis(
                    MarketCategory.NORMAL_MARKET,
                    selected=True,
                    selected_candidate_id="normal-1",
                    candidates=[
                        {
                            "candidate_id": "normal-1",
                            "strategy": "trend_pullback",
                            "direction": "long",
                            "outcome": "accepted",
                            "final_score": 80.0,
                            "reasons": [],
                        }
                    ],
                ),
                _analysis(
                    MarketCategory.GAINER,
                    selected=False,
                    no_trade_reason="no Phase 4 candidates were generated",
                ),
            ),
            failures={},
        ),
    )

    payload = build_futures_pipeline_diagnostics(scan)

    assert set(payload["phase5_analyses"]) == {
        "BTC/USDT:NORMAL_MARKET",
        "BTC/USDT:GAINER",
    }
    assert payload["phase5_summary"]["analysis_funnel"] == {
        "observed": 2,
        "with_candidates": 1,
        "selected": 1,
        "no_trade": 1,
    }
