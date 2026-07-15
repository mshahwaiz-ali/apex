"""Tests for the canonical spot-analysis JSON boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from apex.application.spot_analysis import spot_analysis_result_to_payload
from apex.application.spot_analysis_io import (
    analyze_spot_from_files,
    load_spot_analysis_input,
    write_spot_analysis_result,
)

FIXTURES = Path("tests/fixtures/spot")


def _analyze(name: str):
    return analyze_spot_from_files(input_path=FIXTURES / name)


def _assert_no_futures_fields(value: Any) -> None:
    forbidden = {"leverage", "liquidation", "margin", "maintenance_margin"}
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for nested in value.values():
            _assert_no_futures_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_futures_fields(nested)


def test_approved_json_input_builds_complete_plan() -> None:
    result = _analyze("approved_trend_pullback.json")
    payload = spot_analysis_result_to_payload(result)

    assert payload["selected_strategy"]["decision"] == "APPROVE"
    assert payload["planning"] is not None
    assert payload["planning"]["entry_plan"]["direction"] == "LONG"
    assert payload["planning"]["entry_plan"]["side"] == "BUY"


def test_blocked_json_input_returns_candidates_without_plan() -> None:
    payload = spot_analysis_result_to_payload(_analyze("blocked_risk_off.json"))

    assert payload["selected_strategy"] is None
    assert payload["planning"] is None
    assert len(payload["candidates"]) == 6


def test_output_json_round_trip_is_stable(tmp_path: Path) -> None:
    result = _analyze("approved_trend_pullback.json")
    output = tmp_path / "spot-analysis.json"

    write_spot_analysis_result(output, result)

    assert json.loads(output.read_text(encoding="utf-8")) == spot_analysis_result_to_payload(result)
    assert output.read_text(encoding="utf-8").endswith("\n")


def test_non_object_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        load_spot_analysis_input(path)


def test_unknown_fields_are_rejected(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "approved_trend_pullback.json").read_text(encoding="utf-8"))
    payload["unexpected"] = True
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_spot_analysis_input(path)


def test_invalid_spot_geometry_is_rejected() -> None:
    with pytest.raises(ValidationError, match="spot support must be below resistance"):
        load_spot_analysis_input(FIXTURES / "malformed_geometry.json")


def test_output_contains_no_futures_only_fields() -> None:
    _assert_no_futures_fields(
        spot_analysis_result_to_payload(_analyze("approved_trend_pullback.json"))
    )
