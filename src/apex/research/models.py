"""Deterministic classical-ML selection, validation-only calibration and artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]
from sklearn.isotonic import IsotonicRegression  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.pipeline import make_pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from apex.research.metrics import brier_score, expected_calibration_error


class ModelFamily(StrEnum):
    ENTRY_FILL = "entry_fill"
    POST_FILL_OUTCOME = "post_fill_outcome"
    EARLY_WARNING = "early_warning"


@dataclass(frozen=True, slots=True)
class ModelArtifactManifest:
    schema_version: int
    model_version: str
    family: str
    feature_schema: tuple[str, ...]
    dataset_hash: str
    config_hash: str
    code_hash: str
    training_start: str
    training_end: str
    calibration_start: str
    calibration_end: str
    final_test_start: str
    final_test_end: str
    selected_estimator: str
    validation_brier: float
    final_test_brier: float
    final_test_calibration_error: float
    sample_size: int
    artifact_sha256: str
    created_at: str


@dataclass(slots=True)
class IsotonicCalibratedClassifier:
    estimator: Any
    classes: tuple[int, ...]
    calibrators: tuple[IsotonicRegression, ...]

    def predict_proba(self, features: list[list[float]]) -> list[list[float]]:
        raw = self.estimator.predict_proba(features)
        rows: list[list[float]] = []
        for probabilities in raw:
            calibrated = [
                float(calibrator.predict([float(probability)])[0])
                for calibrator, probability in zip(self.calibrators, probabilities, strict=True)
            ]
            total = sum(calibrated)
            rows.append(
                [value / total for value in calibrated]
                if total > 0
                else [1.0 / len(calibrated)] * len(calibrated)
            )
        return rows


def train_model_family(
    family: ModelFamily,
    *,
    feature_names: tuple[str, ...],
    training_features: list[list[float]],
    training_labels: list[int],
    calibration_features: list[list[float]],
    calibration_labels: list[int],
    final_features: list[list[float]],
    final_labels: list[int],
) -> tuple[IsotonicCalibratedClassifier, dict[str, float | str]]:
    """Compare fixed-seed LR/HGB on one validation partition, then calibrate there only."""

    if not feature_names or any(len(row) != len(feature_names) for row in training_features):
        raise ValueError("feature schema does not match training rows")
    if min(map(len, (training_labels, calibration_labels, final_labels))) < 2:
        raise ValueError("each chronological partition requires at least two rows")
    estimators: dict[str, Any] = {
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(C=0.5, max_iter=1000, class_weight="balanced", random_state=1729),
        ),
        "histogram_gradient_boosting": HistGradientBoostingClassifier(
            learning_rate=0.06,
            max_iter=150,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            class_weight="balanced",
            random_state=1729,
        ),
    }
    scored: list[tuple[float, str, Any]] = []
    for name, estimator in estimators.items():
        estimator.fit(training_features, training_labels)
        probabilities = estimator.predict_proba(calibration_features)
        classes = tuple(int(value) for value in estimator.classes_)
        scored.append(
            (_multiclass_brier(calibration_labels, probabilities, classes), name, estimator)
        )
    validation_brier, selected_name, selected = min(scored, key=lambda item: (item[0], item[1]))
    classes = tuple(int(value) for value in selected.classes_)
    raw_calibration = selected.predict_proba(calibration_features)
    calibrators = tuple(
        IsotonicRegression(out_of_bounds="clip").fit(
            [float(row[index]) for row in raw_calibration],
            [1 if label == class_value else 0 for label in calibration_labels],
        )
        for index, class_value in enumerate(classes)
    )
    calibrated = IsotonicCalibratedClassifier(selected, classes, calibrators)
    final_probabilities = calibrated.predict_proba(final_features)
    final_brier = _multiclass_brier(final_labels, final_probabilities, classes)
    confidence = [max(row) for row in final_probabilities]
    correctness = [
        int(classes[row.index(max(row))] == label)
        for row, label in zip(final_probabilities, final_labels, strict=True)
    ]
    return calibrated, {
        "family": family.value,
        "selected_estimator": selected_name,
        "validation_brier": validation_brier,
        "final_test_brier": final_brier,
        "final_test_calibration_error": expected_calibration_error(correctness, confidence),
    }


def save_trusted_artifact(
    path: Path,
    model: IsotonicCalibratedClassifier,
    manifest_fields: dict[str, Any],
) -> ModelArtifactManifest:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)
    digest = hashlib.sha256(blob).hexdigest()
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(blob)
    os.replace(temporary, path)
    manifest = ModelArtifactManifest(
        schema_version=1,
        artifact_sha256=digest,
        created_at=datetime.now(UTC).isoformat(),
        **manifest_fields,
    )
    path.with_suffix(path.suffix + ".manifest.json").write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n"
    )
    return manifest


def load_trusted_artifact(
    path: Path, *, feature_schema: tuple[str, ...], model_version: str
) -> tuple[IsotonicCalibratedClassifier | None, str]:
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    if not path.exists() or not manifest_path.exists():
        return None, "historical edge unavailable: artifact missing"
    try:
        manifest_payload = json.loads(manifest_path.read_text())
        manifest_payload["feature_schema"] = tuple(manifest_payload["feature_schema"])
        manifest = ModelArtifactManifest(**manifest_payload)
        blob = path.read_bytes()
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None, "historical edge unavailable: invalid manifest"
    if manifest.model_version != model_version or manifest.feature_schema != feature_schema:
        return None, "historical edge unavailable: artifact incompatible"
    if hashlib.sha256(blob).hexdigest() != manifest.artifact_sha256:
        return None, "historical edge unavailable: integrity check failed"
    model = pickle.loads(blob)
    if not isinstance(model, IsotonicCalibratedClassifier):
        return None, "historical edge unavailable: unexpected artifact type"
    return model, "historical edge available"


def _multiclass_brier(labels: list[int], probabilities: Any, classes: tuple[int, ...]) -> float:
    if len(classes) == 2:
        positive = classes[-1]
        return brier_score(
            [int(label == positive) for label in labels],
            [float(row[-1]) for row in probabilities],
        )
    return sum(
        sum(
            (float(label == class_value) - float(row[index])) ** 2
            for index, class_value in enumerate(classes)
        )
        for label, row in zip(labels, probabilities, strict=True)
    ) / len(labels)


__all__ = [
    "IsotonicCalibratedClassifier",
    "ModelArtifactManifest",
    "ModelFamily",
    "load_trusted_artifact",
    "save_trusted_artifact",
    "train_model_family",
]
