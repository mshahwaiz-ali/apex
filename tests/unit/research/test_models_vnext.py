from __future__ import annotations

from apex.research.models import ModelFamily, train_model_family


def test_model_selection_and_isotonic_calibration_are_deterministic() -> None:
    training_x = [[float(index), float(index % 3)] for index in range(30)]
    training_y = [int(index >= 15) for index in range(30)]
    calibration_x = [[float(index), float(index % 3)] for index in range(30, 40)]
    calibration_y = [1] * 8 + [0] * 2
    final_x = [[float(index), float(index % 3)] for index in range(40, 50)]
    final_y = [1] * 7 + [0] * 3

    first_model, first_metrics = train_model_family(
        ModelFamily.ENTRY_FILL,
        feature_names=("trend", "regime"),
        training_features=training_x,
        training_labels=training_y,
        calibration_features=calibration_x,
        calibration_labels=calibration_y,
        final_features=final_x,
        final_labels=final_y,
    )
    second_model, second_metrics = train_model_family(
        ModelFamily.ENTRY_FILL,
        feature_names=("trend", "regime"),
        training_features=training_x,
        training_labels=training_y,
        calibration_features=calibration_x,
        calibration_labels=calibration_y,
        final_features=final_x,
        final_labels=final_y,
    )

    assert first_metrics == second_metrics
    assert first_model.predict_proba(final_x) == second_model.predict_proba(final_x)
