from __future__ import annotations

from copy import deepcopy

import pytest

from apex.config import FileSettings, MethodologySettings


def test_methodology_defaults_are_complete() -> None:
    settings = MethodologySettings()

    assert set(settings.lane_geometry) == {
        "cmp_scalp",
        "confirmation_scalp",
        "pullback_scalp",
        "nearby_structured",
        "runner",
        "developing",
    }
    assert settings.lane_geometry["runner"].minimum_tp1_reward_to_risk == 1.8
    assert settings.lane_geometry["runner"].minimum_target_quality == 60.0
    assert sum(settings.ranking_weights.model_dump().values()) == pytest.approx(1.0)


def test_file_settings_use_methodology_defaults() -> None:
    assert FileSettings().methodology == MethodologySettings()


def test_methodology_rejects_missing_lane() -> None:
    payload = MethodologySettings().model_dump()
    payload["lane_geometry"] = deepcopy(payload["lane_geometry"])
    del payload["lane_geometry"]["runner"]

    with pytest.raises(ValueError, match="missing lanes: runner"):
        MethodologySettings.model_validate(payload)


def test_methodology_rejects_invalid_ranking_weight_total() -> None:
    payload = MethodologySettings().model_dump()
    payload["ranking_weights"]["execution_precedence"] = 0.50

    with pytest.raises(ValueError, match=r"must sum to 1\.0"):
        MethodologySettings.model_validate(payload)


def test_methodology_rejects_unknown_fields() -> None:
    payload = MethodologySettings().model_dump()
    payload["silent_permissive_fallback"] = True

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        MethodologySettings.model_validate(payload)


def test_methodology_rejects_non_positive_htf_target_ceiling() -> None:
    payload = MethodologySettings().model_dump()
    payload["htf_consequences"]["countertrend_scalp_target_ceiling_r"] = 0.0

    with pytest.raises(ValueError, match="greater than 0"):
        MethodologySettings.model_validate(payload)
