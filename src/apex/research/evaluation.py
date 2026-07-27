"""Purged walk-forward evaluation and fail-closed balanced-edge promotion."""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from apex.research.experiment import ExperimentManifest
from apex.research.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
    probability_of_backtest_overfitting,
)


@dataclass(frozen=True, slots=True)
class EvaluationOutcome:
    configuration_id: str
    timestamp: datetime
    symbol: str
    cohort: str
    net_return_r: float
    probability: float | None = None
    label: int | None = None
    strategy_family: str = "unknown"
    timeframe: str = "unknown"
    geometry_profile: str = "canonical"
    evaluation_population: str = "canonical"
    executed: bool = True
    decision_state: str = "executed"

    def __post_init__(self) -> None:
        if not self.configuration_id.strip() or not self.symbol.strip() or not self.cohort.strip():
            raise ValueError("evaluation outcome identities cannot be empty")
        if (
            not self.strategy_family.strip()
            or not self.timeframe.strip()
            or not self.geometry_profile.strip()
            or not self.evaluation_population.strip()
            or not self.decision_state.strip()
        ):
            raise ValueError("evaluation shadow-matrix identities cannot be empty")
        if self.evaluation_population not in {"canonical", "shadow"}:
            raise ValueError("evaluation population must be canonical or shadow")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("evaluation outcome timestamp must be timezone-aware")
        if not math.isfinite(self.net_return_r):
            raise ValueError("evaluation outcome return must be finite")
        if (self.probability is None) != (self.label is None):
            raise ValueError("evaluation probability and label must be provided together")
        if self.probability is not None and not 0.0 <= self.probability <= 1.0:
            raise ValueError("evaluation probability must be in the unit interval")
        if self.label is not None and self.label not in {0, 1}:
            raise ValueError("evaluation label must be binary")


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    fold: int
    training_timestamps: tuple[datetime, ...]
    validation_timestamps: tuple[datetime, ...]
    purged_timestamps: tuple[datetime, ...]


@dataclass(frozen=True, slots=True)
class WalkForwardDesign:
    folds: tuple[WalkForwardFold, ...]
    final_test_timestamps: tuple[datetime, ...]
    final_boundary_purged: tuple[datetime, ...]
    final_boundary_embargoed: tuple[datetime, ...]


def purged_walk_forward_design(
    timestamps: Iterable[datetime],
    *,
    fold_count: int,
    purge_bars: int,
    embargo_bars: int,
) -> WalkForwardDesign:
    """Create expanding folds and one final 20% holdout using timestamp groups."""

    ordered = tuple(sorted(set(timestamps)))
    if any(item.tzinfo is None or item.utcoffset() is None for item in ordered):
        raise ValueError("walk-forward timestamps must be timezone-aware")
    if fold_count < 2 or purge_bars < 0 or embargo_bars < 0:
        raise ValueError("walk-forward fold, purge, and embargo settings are invalid")
    if len(ordered) < max(10, fold_count * 2 + purge_bars + embargo_bars + 2):
        raise ValueError("insufficient unique timestamps for requested walk-forward design")

    development_end = max(2, int(len(ordered) * 0.80))
    initial_training = max(2, development_end // (fold_count + 1))
    validation_width = max(1, (development_end - initial_training) // fold_count)
    folds: list[WalkForwardFold] = []
    for fold_index in range(fold_count):
        raw_training_end = initial_training + fold_index * validation_width
        validation_start = raw_training_end + embargo_bars
        validation_end = (
            development_end
            if fold_index == fold_count - 1
            else min(development_end, validation_start + validation_width)
        )
        training_end = max(0, raw_training_end - purge_bars)
        training = ordered[:training_end]
        validation = ordered[validation_start:validation_end]
        if not training or not validation:
            raise ValueError("purge/embargo produced an empty walk-forward partition")
        folds.append(
            WalkForwardFold(
                fold=fold_index + 1,
                training_timestamps=training,
                validation_timestamps=validation,
                purged_timestamps=ordered[training_end:raw_training_end],
            )
        )

    final_train_end = max(0, development_end - purge_bars)
    final_start = min(len(ordered), development_end + embargo_bars)
    final_test = ordered[final_start:]
    if not final_test:
        raise ValueError("purge/embargo produced an empty final-test partition")
    return WalkForwardDesign(
        folds=tuple(folds),
        final_test_timestamps=final_test,
        final_boundary_purged=ordered[final_train_end:development_end],
        final_boundary_embargoed=ordered[development_end:final_start],
    )


def reliability_diagram(
    labels: Sequence[int],
    probabilities: Sequence[float],
    *,
    bins: int = 10,
) -> tuple[dict[str, float | int], ...]:
    if bins < 2 or not labels or len(labels) != len(probabilities):
        raise ValueError("reliability diagram requires aligned observations and at least two bins")
    result: list[dict[str, float | int]] = []
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        selected = tuple(
            row
            for row, probability in enumerate(probabilities)
            if lower <= probability < upper or (index == bins - 1 and probability == 1.0)
        )
        result.append(
            {
                "lower": lower,
                "upper": upper,
                "count": len(selected),
                "mean_probability": (
                    fmean(probabilities[row] for row in selected) if selected else 0.0
                ),
                "event_rate": fmean(labels[row] for row in selected) if selected else 0.0,
            }
        )
    return tuple(result)


def brier_decomposition(
    labels: Sequence[int],
    probabilities: Sequence[float],
    *,
    bins: int = 10,
) -> dict[str, float]:
    diagram = reliability_diagram(labels, probabilities, bins=bins)
    base_rate = fmean(labels)
    total = len(labels)
    reliability = sum(
        int(item["count"])
        / total
        * (float(item["mean_probability"]) - float(item["event_rate"])) ** 2
        for item in diagram
    )
    resolution = sum(
        int(item["count"]) / total * (float(item["event_rate"]) - base_rate) ** 2
        for item in diagram
    )
    uncertainty = base_rate * (1.0 - base_rate)
    return {
        "brier_score": brier_score(labels, probabilities),
        "reliability": reliability,
        "resolution": resolution,
        "uncertainty": uncertainty,
        "decomposed_brier": reliability - resolution + uncertainty,
    }


def bootstrap_mean_lower_bound(
    values: Sequence[float],
    *,
    samples: int,
    confidence: float = 0.95,
    seed: int = 1729,
) -> float:
    if not values or samples < 100 or not 0.0 < confidence < 1.0:
        raise ValueError("bootstrap inputs are invalid")
    generator = random.Random(seed)
    estimates = sorted(
        fmean(values[generator.randrange(len(values))] for _ in values) for _ in range(samples)
    )
    index = max(0, math.floor((1.0 - confidence) * len(estimates)))
    return estimates[min(index, len(estimates) - 1)]


def evaluate_walk_forward_campaign(
    outcomes: Sequence[EvaluationOutcome],
    manifest: ExperimentManifest,
) -> dict[str, Any]:
    """Evaluate candidates, then unlock the final test once for the validation winner."""

    if not outcomes:
        raise ValueError("walk-forward evaluation requires outcomes")
    configuration_ids = tuple(manifest.configuration_ids)
    canonical_outcomes = tuple(
        item for item in outcomes if item.evaluation_population == "canonical"
    )
    if not canonical_outcomes:
        raise ValueError("walk-forward evaluation requires canonical decision outcomes")
    observed_ids = {item.configuration_id for item in canonical_outcomes}
    unknown = observed_ids.difference(configuration_ids)
    if unknown:
        raise ValueError(f"outcomes contain undeclared configurations: {sorted(unknown)}")
    missing = set(configuration_ids).difference(observed_ids)
    if missing:
        raise ValueError(f"manifest configurations have no outcomes: {sorted(missing)}")

    design = purged_walk_forward_design(
        (item.timestamp for item in canonical_outcomes),
        fold_count=manifest.fold_count,
        purge_bars=manifest.purge_horizon_bars,
        embargo_bars=manifest.embargo_bars,
    )
    fold_payloads: list[dict[str, object]] = []
    validation_scores: dict[str, list[float]] = defaultdict(list)
    pbo_values: list[float] = []
    for fold in design.folds:
        training_set = set(fold.training_timestamps)
        validation_set = set(fold.validation_timestamps)
        training_scores = [
            _expectancy(
                item.net_return_r
                for item in canonical_outcomes
                if item.configuration_id == config_id and item.timestamp in training_set
            )
            for config_id in configuration_ids
        ]
        validation = [
            _expectancy(
                item.net_return_r
                for item in canonical_outcomes
                if item.configuration_id == config_id and item.timestamp in validation_set
            )
            for config_id in configuration_ids
        ]
        for config_id, score in zip(configuration_ids, validation, strict=True):
            validation_scores[config_id].append(score)
        if len(configuration_ids) >= 2 and (
            len(set(training_scores)) > 1 or len(set(validation)) > 1
        ):
            pbo_values.append(probability_of_backtest_overfitting(training_scores, validation))
        fold_payloads.append(
            {
                "fold": fold.fold,
                "training_timestamp_count": len(fold.training_timestamps),
                "validation_timestamp_count": len(fold.validation_timestamps),
                "purged_timestamp_count": len(fold.purged_timestamps),
                "training_expectancy_by_configuration": dict(
                    zip(configuration_ids, training_scores, strict=True)
                ),
                "validation_expectancy_by_configuration": dict(
                    zip(configuration_ids, validation, strict=True)
                ),
            }
        )

    mean_validation = {config_id: fmean(scores) for config_id, scores in validation_scores.items()}
    selected = max(configuration_ids, key=lambda item: (mean_validation[item], item))
    final_timestamps = set(design.final_test_timestamps)
    final = tuple(
        sorted(
            (
                item
                for item in canonical_outcomes
                if item.configuration_id == selected and item.timestamp in final_timestamps
            ),
            key=lambda item: (item.timestamp, item.symbol, item.cohort),
        )
    )
    if not final:
        raise ValueError("selected configuration has no untouched final-test outcomes")
    returns = tuple(item.net_return_r for item in final)
    executed_final = tuple(item for item in final if item.executed)
    expectancy = fmean(returns)
    profit_factor = _profit_factor(returns)
    maximum_drawdown = _maximum_drawdown(returns)
    lower_bound = bootstrap_mean_lower_bound(
        returns,
        samples=manifest.bootstrap_samples,
    )
    by_cohort = _group_expectancy(final, "cohort")
    by_symbol = _group_expectancy(final, "symbol")
    by_month = _month_expectancy(final)
    exclusion = {
        "without_best_symbol_expectancy_r": _expectancy_without_best(final, by_symbol, "symbol"),
        "without_best_month_expectancy_r": _expectancy_without_best(final, by_month, "month"),
    }
    calibration = _calibration_payload(executed_final)
    shadow_matrix = _shadow_matrix_payload(outcomes, manifest)
    pbo = fmean(pbo_values) if len(pbo_values) >= 2 else None
    pbo_reason = (
        None
        if pbo is not None
        else "requires_multiple_configurations_and_fold_level_vectors"
        if len(configuration_ids) < 2
        else "configuration_vectors_have_no_cross_sectional_variance"
    )
    failed_gates: list[str] = []
    if not manifest.final_test_untouched:
        failed_gates.append("manifest does not reserve an untouched final test")
    if len(executed_final) < manifest.minimum_final_test_outcomes:
        failed_gates.append("insufficient untouched final-test outcomes")
    if lower_bound <= 0.0:
        failed_gates.append("95% bootstrap expectancy lower bound is not above zero")
    if (profit_factor is not None and profit_factor <= 1.0) or (
        profit_factor is None and not any(value > 0.0 for value in returns)
    ):
        failed_gates.append("final-test profit factor is not above one")
    if maximum_drawdown > manifest.maximum_drawdown_r:
        failed_gates.append("final-test drawdown exceeds the declared risk budget")
    selected_fold_scores = validation_scores[selected]
    if not selected_fold_scores or any(score <= 0.0 for score in selected_fold_scores):
        failed_gates.append("selected configuration is not positive in every validation fold")
    if any(value <= 0.0 for value in by_cohort.values()):
        failed_gates.append("selected configuration is unstable across observed cohorts")
    if any(value <= 0.0 for value in exclusion.values()):
        failed_gates.append("edge depends on the best symbol or month")
    if len(configuration_ids) < 2 or pbo is None:
        failed_gates.append("PBO unavailable without multiple configurations and folds")
    elif pbo > 0.20:
        failed_gates.append("PBO exceeds 0.20")
    calibration_available = calibration.get("available") is True
    brier_skill_value = calibration.get("brier_skill")
    if manifest.probability_assessment_required and not calibration_available:
        failed_gates.append("required untouched probability calibration is unavailable")
    elif (
        manifest.probability_assessment_required
        and isinstance(brier_skill_value, (int, float))
        and brier_skill_value <= 0.0
    ):
        failed_gates.append("required probability calibration does not beat the base rate")
    shadow_coverage = shadow_matrix["coverage_ratio"]
    if (
        manifest.required_shadow_matrix
        and isinstance(shadow_coverage, (int, float))
        and shadow_coverage < 1.0
    ):
        failed_gates.append("required strategy/timeframe/geometry shadow matrix is incomplete")

    return {
        "schema_version": 1,
        "experiment_fingerprint": manifest.fingerprint,
        "selection_authority": "validation_folds_only",
        "final_test_authority": "unlocked_once_after_configuration_selection",
        "selected_configuration": selected,
        "attempted_configurations": len(configuration_ids),
        "folds": fold_payloads,
        "parameter_sensitivity": {
            "mean_validation_expectancy_r": mean_validation,
            "selected_minus_worst_validation_expectancy_r": (
                mean_validation[selected] - min(mean_validation.values())
            ),
        },
        "pbo": pbo,
        "pbo_reason": pbo_reason,
        "shadow_matrix": shadow_matrix,
        "final_test": {
            "decision_outcomes": len(final),
            "executed_outcomes": len(executed_final),
            "no_trade_outcomes": len(final) - len(executed_final),
            "net_expectancy_r": expectancy,
            "bootstrap_95_lower_bound_r": lower_bound,
            "profit_factor": profit_factor,
            "profit_factor_reason": ("no_losing_outcomes" if profit_factor is None else "computed"),
            "maximum_drawdown_r": maximum_drawdown,
            "by_cohort": by_cohort,
            "by_symbol": by_symbol,
            "by_month": by_month,
            "exclusions": exclusion,
            "calibration": calibration,
        },
        "promotion": {
            "promoted": not failed_gates,
            "failed_gates": failed_gates,
            "authority": (
                "promoted_after_out_of_sample_validation" if not failed_gates else "research_only"
            ),
        },
    }


def load_evaluation_outcomes(path: Path) -> tuple[EvaluationOutcome, ...]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    payloads: list[object]
    if stripped.startswith("{") or stripped.startswith("["):
        document = json.loads(stripped)
        if isinstance(document, dict) and isinstance(document.get("outcome_files"), list):
            combined: list[EvaluationOutcome] = []
            for referenced in document["outcome_files"]:
                combined.extend(load_evaluation_outcomes(path.parent / str(referenced)))
            return tuple(combined)
        if isinstance(document, dict) and isinstance(document.get("evaluation_outcomes"), list):
            payloads = list(document["evaluation_outcomes"])
        elif isinstance(document, list):
            payloads = list(document)
        else:
            payloads = [document]
    else:
        payloads = [json.loads(line) for line in text.splitlines() if line.strip()]
    rows: list[EvaluationOutcome] = []
    for line_number, payload in enumerate(payloads, start=1):
        if not isinstance(payload, dict):
            raise ValueError(f"evaluation outcome line {line_number} must be an object")
        rows.append(
            EvaluationOutcome(
                configuration_id=str(payload["configuration_id"]),
                timestamp=datetime.fromisoformat(str(payload["timestamp"])),
                symbol=str(payload["symbol"]),
                cohort=str(payload["cohort"]),
                net_return_r=float(payload["net_return_r"]),
                probability=(
                    None if payload.get("probability") is None else float(payload["probability"])
                ),
                label=None if payload.get("label") is None else int(payload["label"]),
                strategy_family=str(payload.get("strategy_family", "unknown")),
                timeframe=str(payload.get("timeframe", "unknown")),
                geometry_profile=str(payload.get("geometry_profile", "canonical")),
                evaluation_population=str(payload.get("evaluation_population", "canonical")),
                executed=bool(payload.get("executed", True)),
                decision_state=str(payload.get("decision_state", "executed")),
            )
        )
    return tuple(rows)


def write_evaluation_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _expectancy(values: Iterable[float]) -> float:
    items = tuple(values)
    return fmean(items) if items else 0.0


def _profit_factor(values: Sequence[float]) -> float | None:
    profit = sum(value for value in values if value > 0.0)
    loss = abs(sum(value for value in values if value < 0.0))
    return profit / loss if loss > 0.0 else None


def _maximum_drawdown(values: Sequence[float]) -> float:
    equity = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def _group_expectancy(outcomes: Sequence[EvaluationOutcome], attribute: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in outcomes:
        grouped[str(getattr(item, attribute))].append(item.net_return_r)
    return {key: fmean(values) for key, values in sorted(grouped.items())}


def _month_expectancy(outcomes: Sequence[EvaluationOutcome]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in outcomes:
        grouped[item.timestamp.strftime("%Y-%m")].append(item.net_return_r)
    return {key: fmean(values) for key, values in sorted(grouped.items())}


def _expectancy_without_best(
    outcomes: Sequence[EvaluationOutcome],
    grouped: dict[str, float],
    dimension: str,
) -> float:
    if len(grouped) < 2:
        return 0.0
    best = max(grouped, key=lambda item: (grouped[item], item))
    values = tuple(
        item.net_return_r
        for item in outcomes
        if (item.symbol if dimension == "symbol" else item.timestamp.strftime("%Y-%m")) != best
    )
    return _expectancy(values)


def _calibration_payload(outcomes: Sequence[EvaluationOutcome]) -> dict[str, object]:
    calibrated = tuple(
        item for item in outcomes if item.probability is not None and item.label is not None
    )
    if len(calibrated) != len(outcomes) or not calibrated:
        return {
            "available": False,
            "reason": "complete untouched probabilities and binary labels are required",
            "brier_skill": 0.0,
        }
    labels = tuple(int(item.label) for item in calibrated if item.label is not None)
    probabilities = tuple(
        float(item.probability) for item in calibrated if item.probability is not None
    )
    return {
        "available": True,
        "brier_score": brier_score(labels, probabilities),
        "brier_skill": brier_skill_score(labels, probabilities),
        "expected_calibration_error": expected_calibration_error(labels, probabilities),
        "brier_decomposition": brier_decomposition(labels, probabilities),
        "reliability_diagram": reliability_diagram(labels, probabilities),
    }


def _shadow_matrix_payload(
    outcomes: Sequence[EvaluationOutcome],
    manifest: ExperimentManifest,
) -> dict[str, object]:
    declared = {
        (strategy, timeframe, geometry)
        for strategy in manifest.strategy_families
        for timeframe in manifest.timeframes
        for geometry in manifest.geometry_profiles
    }
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for item in outcomes:
        if item.evaluation_population != "shadow":
            continue
        grouped[(item.strategy_family, item.timeframe, item.geometry_profile)].append(
            item.net_return_r
        )
    observed_declared = declared.intersection(grouped)
    cells = [
        {
            "strategy_family": key[0],
            "timeframe": key[1],
            "geometry_profile": key[2],
            "outcomes": len(values),
            "net_expectancy_r": fmean(values),
        }
        for key, values in sorted(grouped.items())
    ]
    return {
        "authority": "shadow_only",
        "declared_cell_count": len(declared),
        "observed_declared_cell_count": len(observed_declared),
        "unobserved_declared_cell_count": len(declared - observed_declared),
        "coverage_ratio": len(observed_declared) / len(declared) if declared else 0.0,
        "cells": cells,
    }


__all__ = [
    "EvaluationOutcome",
    "WalkForwardDesign",
    "WalkForwardFold",
    "bootstrap_mean_lower_bound",
    "brier_decomposition",
    "evaluate_walk_forward_campaign",
    "load_evaluation_outcomes",
    "purged_walk_forward_design",
    "reliability_diagram",
    "write_evaluation_report",
]
