"""Tests for the provider-independent spot-orchestration JSON boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from apex.application.spot_analysis import spot_analysis_result_to_payload
from apex.application.spot_orchestration import build_spot_strategy_input
from apex.application.spot_orchestration_io import (
    analyze_spot_orchestration_from_files,
    load_spot_orchestration_input,
    write_spot_orchestration_result,
)

FIXTURES = Path("tests/fixtures/spot_orchestration")


def _analyze(name: str):
    return analyze_spot_orchestration_from_files(input_path=FIXTURES / name)


def _assert_no_futures_fields(value: Any) -> None:
    forbidden = {
        "leverage",
        "liquidation",
        "margin",
        "maintenance_margin",
        "short",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for nested in value.values():
            _assert_no_futures_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_futures_fields(nested)


def _fixture_payload(name: str) -> dict[str, Any]:
    loaded = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_approved_orchestration_selects_strategy_and_plan() -> None:
    payload = spot_analysis_result_to_payload(_analyze("approved_trend_pullback.json"))

    assert payload["selected_strategy"]["strategy"] == "higher_timeframe_trend_pullback"
    assert payload["selected_strategy"]["decision"] == "APPROVE"
    assert payload["planning"] is not None


def test_risk_off_orchestration_produces_no_plan() -> None:
    payload = spot_analysis_result_to_payload(_analyze("blocked_risk_off.json"))

    assert payload["selected_strategy"] is None
    assert payload["planning"] is None
    assert len(payload["candidates"]) == 6


@pytest.mark.parametrize("extension", ["TERMINAL", "DOWNSIDE_RISK"])
def test_terminal_or_downside_structure_blocks_planning(
    tmp_path: Path,
    extension: str,
) -> None:
    payload = _fixture_payload("approved_trend_pullback.json")
    payload["structure"]["extension"] = extension
    payload["structure"]["timeframes"][0]["extension"] = extension
    path = tmp_path / f"{extension.lower()}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = analyze_spot_orchestration_from_files(input_path=path)

    assert result.routing.selected is None
    assert result.planning is None


def test_missing_optional_evidence_remains_unconfirmed() -> None:
    input_model = load_spot_orchestration_input(FIXTURES / "missing_evidence.json")
    strategy_input = build_spot_strategy_input(input_model)
    result = _analyze("missing_evidence.json")

    assert strategy_input.volume_ratio == 0.0
    assert strategy_input.pullback_depth_percentage is None
    assert strategy_input.breakout_confirmed is False
    assert strategy_input.retest_held is False
    assert result.routing.selected is None
    assert result.planning is None


def test_unknown_fields_are_rejected(tmp_path: Path) -> None:
    payload = _fixture_payload("approved_trend_pullback.json")
    payload["unexpected"] = True
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_spot_orchestration_input(path)


def test_non_object_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        load_spot_orchestration_input(path)


def test_malformed_structure_is_rejected() -> None:
    with pytest.raises(ValidationError):
        load_spot_orchestration_input(FIXTURES / "malformed_structure.json")


def test_invalid_geometry_is_rejected() -> None:
    with pytest.raises(ValidationError, match="canonical spot support must be below resistance"):
        load_spot_orchestration_input(FIXTURES / "malformed_geometry.json")


def test_output_file_roundtrip_matches_payload(tmp_path: Path) -> None:
    result = _analyze("approved_trend_pullback.json")
    output = tmp_path / "spot-orchestration.json"

    write_spot_orchestration_result(output, result)

    assert json.loads(output.read_text(encoding="utf-8")) == spot_analysis_result_to_payload(result)
    assert output.read_text(encoding="utf-8").endswith("\n")


def test_repeated_execution_is_deterministic() -> None:
    first = spot_analysis_result_to_payload(_analyze("approved_trend_pullback.json"))
    second = spot_analysis_result_to_payload(_analyze("approved_trend_pullback.json"))

    assert first == second


def test_output_contains_no_futures_only_fields_recursively() -> None:
    _assert_no_futures_fields(
        spot_analysis_result_to_payload(_analyze("approved_trend_pullback.json"))
    )
