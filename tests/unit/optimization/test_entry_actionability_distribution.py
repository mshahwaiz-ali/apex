"""Tests for entry-actionability distribution adaptation."""

from __future__ import annotations

from apex.optimization.contracts import (
    CandidateParameterSet,
    OptimizationDecision,
    OptimizationGroup,
    OptimizationResult,
    OptimizationRunConfig,
)
from apex.optimization.engine import (
    performance_from_campaign_payload,
    performance_from_mapping,
    result_to_payload,
)


def test_performance_mapping_preserves_entry_actionability_counts() -> None:
    summary = performance_from_mapping(
        {
            "metrics": {
                "total_trades": 12,
                "by_entry_actionability": {
                    "READY": 4,
                    "AGGRESSIVE": 3,
                    "PULLBACK_PREFERRED": 2,
                    "WATCH": 1,
                    "LATE": 1,
                    "INVALID": 1,
                },
            }
        }
    )

    assert summary.by_entry_actionability == {
        "READY": 4,
        "AGGRESSIVE": 3,
        "PULLBACK_PREFERRED": 2,
        "WATCH": 1,
        "LATE": 1,
        "INVALID": 1,
    }


def test_campaign_payload_aggregates_entry_actionability_counts() -> None:
    summary = performance_from_campaign_payload(
        {
            "best_variant_id": "candidate",
            "variants": [
                {
                    "variant": {"identifier": "candidate"},
                    "symbol": "BTCUSDT",
                    "metrics": {
                        "total_trades": 3,
                        "by_entry_actionability": {"READY": 2, "AGGRESSIVE": 1},
                    },
                },
                {
                    "variant": {"identifier": "candidate"},
                    "symbol": "ETHUSDT",
                    "metrics": {
                        "total_trades": 4,
                        "by_entry_actionability": {
                            "READY": 1,
                            "PULLBACK_PREFERRED": 3,
                        },
                    },
                },
            ],
        }
    )

    assert summary.by_entry_actionability == {
        "READY": 3,
        "AGGRESSIVE": 1,
        "PULLBACK_PREFERRED": 3,
    }


def test_optimization_payload_serializes_entry_actionability_counts() -> None:
    summary = performance_from_mapping(
        {
            "metrics": {
                "total_trades": 2,
                "by_entry_actionability": {"READY": 1, "AGGRESSIVE": 1},
            }
        }
    )
    run_config = OptimizationRunConfig(
        identifier="entry-actionability-test",
        variable_group=OptimizationGroup.SCORING_THRESHOLDS,
    )
    parameter_set = CandidateParameterSet(
        identifier="candidate",
        group=OptimizationGroup.SCORING_THRESHOLDS,
        parameters={"minimum_score": 70},
    )
    result = OptimizationResult(
        decision=OptimizationDecision.ACCEPTED,
        run_config=run_config,
        baseline=summary,
        candidate=summary,
        parameter_set=parameter_set,
        reasons=("test result",),
        recommended_patch={},
    )

    payload = result_to_payload(result)

    assert payload["candidate"]["by_entry_actionability"] == {
        "READY": 1,
        "AGGRESSIVE": 1,
    }
