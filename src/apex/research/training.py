"""Campaign feature-row training for all three locked model families."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from apex.research.models import ModelFamily, save_trusted_artifact, train_model_family
from apex.research.precision import (
    precision_frontier,
    select_validation_threshold,
)
from apex.research.splits import grouped_chronological_split


def train_campaign_models(dataset_dir: Path) -> dict[str, object]:
    """Train from point-in-time production feature rows written by campaign generation."""

    rows_path = dataset_dir / "feature_rows.jsonl"
    if not rows_path.exists():
        return {"trained": False, "reason": "feature_rows.jsonl is not present"}
    rows = tuple(json.loads(line) for line in rows_path.read_text().splitlines() if line.strip())
    dataset_hash = hashlib.sha256(rows_path.read_bytes()).hexdigest()
    artifacts: dict[str, object] = {}
    for family in ModelFamily:
        family_rows = sorted(
            (row for row in rows if row.get("family") == family.value),
            key=lambda row: str(row["timestamp"]),
        )
        if len(family_rows) < 30:
            artifacts[family.value] = {"trained": False, "reason": "fewer than 30 rows"}
            continue
        timestamps = tuple(datetime.fromisoformat(str(row["timestamp"])) for row in family_rows)
        split = grouped_chronological_split(
            timestamps,
            tuple(str(row.get("group_id") or row["timestamp"]) for row in family_rows),
            horizon=timedelta(hours=24),
            embargo=timedelta(hours=1),
        )
        if min(len(split.training), len(split.calibration), len(split.final_test)) < 2:
            artifacts[family.value] = {
                "trained": False,
                "reason": "purge/embargo leaves an undersized partition",
            }
            continue
        feature_schema = tuple(sorted(str(key) for key in family_rows[0]["features"]))
        if any(tuple(sorted(row["features"])) != feature_schema for row in family_rows):
            artifacts[family.value] = {"trained": False, "reason": "feature schema drift"}
            continue
        matrix = [[float(row["features"][name]) for name in feature_schema] for row in family_rows]
        labels = [int(row["label"]) for row in family_rows]
        if len({labels[index] for index in split.training}) < 2:
            artifacts[family.value] = {
                "trained": False,
                "reason": "training partition contains fewer than two classes",
            }
            continue
        model, metrics = train_model_family(
            family,
            feature_names=feature_schema,
            training_features=_select(matrix, split.training),
            training_labels=_select(labels, split.training),
            calibration_features=_select(matrix, split.calibration),
            calibration_labels=_select(labels, split.calibration),
            final_features=_select(matrix, split.final_test),
            final_labels=_select(labels, split.final_test),
        )
        artifact_path = dataset_dir / "models" / f"{family.value}.pkl"
        manifest = save_trusted_artifact(
            artifact_path,
            model,
            {
                "model_version": "apex-vnext-1",
                "family": family.value,
                "feature_schema": feature_schema,
                "dataset_hash": dataset_hash,
                "config_hash": str(family_rows[0].get("config_hash", "unknown")),
                "code_hash": str(family_rows[0].get("code_hash", "unknown")),
                "training_start": timestamps[split.training[0]].isoformat(),
                "training_end": timestamps[split.training[-1]].isoformat(),
                "calibration_start": timestamps[split.calibration[0]].isoformat(),
                "calibration_end": timestamps[split.calibration[-1]].isoformat(),
                "final_test_start": timestamps[split.final_test[0]].isoformat(),
                "final_test_end": timestamps[split.final_test[-1]].isoformat(),
                "selected_estimator": str(metrics["selected_estimator"]),
                "validation_brier": float(metrics["validation_brier"]),
                "final_test_brier": float(metrics["final_test_brier"]),
                "final_test_calibration_error": float(metrics["final_test_calibration_error"]),
                "sample_size": len(family_rows),
            },
        )
        artifact_summary: dict[str, object] = {
            "trained": True,
            "artifact": str(artifact_path),
            "manifest": str(artifact_path.with_suffix(".pkl.manifest.json")),
            "artifact_sha256": manifest.artifact_sha256,
            "metrics": metrics,
        }
        artifacts[family.value] = artifact_summary
        if family is ModelFamily.POST_FILL_OUTCOME and all(
            "net_r" in family_rows[index] for index in (*split.calibration, *split.final_test)
        ):
            positive_index = model.classes.index(1)
            validation_probabilities = [
                row[positive_index]
                for row in model.predict_proba(_select(matrix, split.calibration))
            ]
            frontier = precision_frontier(
                validation_probabilities,
                [float(family_rows[index]["net_r"]) for index in split.calibration],
                minimum_outcomes=min(50, len(split.calibration)),
            )
            selected_threshold = select_validation_threshold(frontier)
            artifact_summary["validation_precision_frontier"] = [
                {
                    "threshold": point.threshold,
                    "outcomes": point.outcomes,
                    "wins": point.wins,
                    "win_rate": point.win_rate,
                    "expectancy_r": point.expectancy_r,
                    "profit_factor": point.profit_factor,
                    "break_even_win_rate": point.break_even_win_rate,
                    "eligible": point.eligible,
                }
                for point in frontier
            ]
            artifact_summary["selected_threshold"] = (
                None if selected_threshold is None else selected_threshold.threshold
            )
            if selected_threshold is not None:
                final_probabilities = [
                    row[positive_index]
                    for row in model.predict_proba(_select(matrix, split.final_test))
                ]
                final_point = precision_frontier(
                    final_probabilities,
                    [float(family_rows[index]["net_r"]) for index in split.final_test],
                    thresholds=(selected_threshold.threshold,),
                    minimum_outcomes=1,
                )[0]
                artifact_summary["untouched_final_precision"] = {
                    "threshold": final_point.threshold,
                    "outcomes": final_point.outcomes,
                    "wins": final_point.wins,
                    "win_rate": final_point.win_rate,
                    "expectancy_r": final_point.expectancy_r,
                    "profit_factor": final_point.profit_factor,
                    "break_even_win_rate": final_point.break_even_win_rate,
                }
    return {
        "trained": any(
            isinstance(item, dict) and item.get("trained") is True for item in artifacts.values()
        ),
        "families": artifacts,
    }


def _select(values: list[Any], indexes: tuple[int, ...]) -> list[Any]:
    return [values[index] for index in indexes]


__all__ = ["train_campaign_models"]
