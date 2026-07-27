from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apex.research.evaluation import (
    EvaluationOutcome,
    brier_decomposition,
    evaluate_walk_forward_campaign,
    load_evaluation_outcomes,
    purged_walk_forward_design,
)
from apex.research.experiment import default_experiment_manifest


def _outcomes() -> tuple[EvaluationOutcome, ...]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    rows: list[EvaluationOutcome] = []
    for index in range(120):
        timestamp = start + timedelta(days=index)
        for configuration_id in ("stable", "weak"):
            positive = index % 4 != 0
            value = (
                (0.5 if positive else -0.1)
                if configuration_id == "stable"
                else (0.1 if positive else -0.4)
            )
            rows.append(
                EvaluationOutcome(
                    configuration_id=configuration_id,
                    timestamp=timestamp,
                    symbol="BTCUSDT" if index % 2 else "ETHUSDT",
                    cohort="directional" if index % 3 else "mixed",
                    net_return_r=value,
                    probability=0.8 if positive else 0.2,
                    label=1 if positive else 0,
                    strategy_family="trend_pullback",
                    timeframe="5m",
                    geometry_profile="canonical",
                )
            )
        rows.append(
            EvaluationOutcome(
                configuration_id="stable",
                timestamp=timestamp,
                symbol="BTCUSDT",
                cohort="directional",
                net_return_r=0.1,
                strategy_family="trend_pullback",
                timeframe="5m",
                geometry_profile="canonical",
                evaluation_population="shadow",
            )
        )
    return tuple(rows)


def test_walk_forward_design_is_purged_embargoed_and_final_is_disjoint() -> None:
    timestamps = tuple(item.timestamp for item in _outcomes())
    design = purged_walk_forward_design(
        timestamps,
        fold_count=3,
        purge_bars=2,
        embargo_bars=2,
    )

    assert len(design.folds) == 3
    assert design.final_boundary_purged
    assert design.final_boundary_embargoed
    assert set(design.final_test_timestamps).isdisjoint(design.folds[-1].validation_timestamps)


def test_walk_forward_report_selects_on_validation_and_reports_final_gates() -> None:
    manifest = replace(
        default_experiment_manifest(
            dataset_fingerprint="a" * 64,
            symbols=("BTCUSDT", "ETHUSDT"),
        ),
        configuration_ids=("stable", "weak"),
        attempted_configurations=2,
        fold_count=3,
        purge_horizon_bars=2,
        embargo_bars=2,
        bootstrap_samples=200,
        minimum_final_test_outcomes=10,
        probability_assessment_required=True,
    )

    report = evaluate_walk_forward_campaign(_outcomes(), manifest)

    assert report["selected_configuration"] == "stable"
    assert report["selection_authority"] == "validation_folds_only"
    assert report["attempted_configurations"] == 2
    assert report["final_test"]["calibration"]["available"] is True
    assert report["shadow_matrix"]["observed_declared_cell_count"] == 1
    assert "promoted" in report["promotion"]


def test_brier_decomposition_reports_all_authority_components() -> None:
    decomposition = brier_decomposition(
        (0, 0, 1, 1),
        (0.1, 0.2, 0.8, 0.9),
        bins=2,
    )

    assert set(decomposition) == {
        "brier_score",
        "reliability",
        "resolution",
        "uncertainty",
        "decomposed_brier",
    }


def test_outcome_loader_accepts_backtest_report_envelope(tmp_path: Path) -> None:
    path = tmp_path / "backtest.json"
    path.write_text(
        json.dumps(
            {
                "evaluation_outcomes": [
                    {
                        "configuration_id": "config",
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "symbol": "BTCUSDT",
                        "cohort": "mixed",
                        "net_return_r": -1.0,
                        "probability": None,
                        "label": None,
                    }
                ]
            }
        )
    )

    loaded = load_evaluation_outcomes(path)

    assert len(loaded) == 1
    assert loaded[0].configuration_id == "config"
