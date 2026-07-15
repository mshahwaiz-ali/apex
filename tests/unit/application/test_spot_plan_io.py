"""Tests for the canonical spot planning JSON boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from apex.application.spot_plan_io import (
    SPOT_PLAN_SCHEMA_VERSION,
    build_spot_plan_from_files,
    load_spot_planning_input,
    spot_planning_result_to_payload,
    write_spot_planning_result,
)


def _planning_payload() -> dict[str, Any]:
    return {
        "candidate": {
            "strategy": "higher_timeframe_trend_pullback",
            "decision": "APPROVE",
            "eligibility": "PAPER_ONLY",
            "thesis": "higher-timeframe uptrend pulled back into demand",
            "invalidation_price": 90.0,
            "evidence": ["weekly trend bullish", "daily demand held"],
        },
        "account": {
            "quote_asset": "USDT",
            "available_quote_balance": 10000.0,
            "total_spot_equity": 10000.0,
            "current_spot_exposure": 0.0,
            "open_position_count": 0,
            "balances": [],
        },
        "current_price": 100.0,
        "support_price": 98.0,
        "resistance_price": 110.0,
        "deeper_support_price": 95.0,
        "recovery_entry_price": 94.0,
        "correlated_sector_exposure": 0.0,
    }


def test_load_build_and_serialize_spot_plan(tmp_path: Path) -> None:
    input_path = tmp_path / "spot-input.json"
    input_path.write_text(json.dumps(_planning_payload()), encoding="utf-8")

    planning_input = load_spot_planning_input(input_path)
    assert planning_input.account.quote_asset == "USDT"

    result = build_spot_plan_from_files(
        input_path=input_path,
        config_path=Path("config/spot.yaml"),
    )
    payload = spot_planning_result_to_payload(result)

    assert payload["schema_version"] == SPOT_PLAN_SCHEMA_VERSION
    assert payload["entry_plan"]["direction"] == "LONG"
    assert payload["entry_plan"]["side"] == "BUY"
    assert payload["position_plan"]["capital_allocated"] <= 2000.0
    assert "leverage" not in payload["position_plan"]
    assert "liquidation" not in payload["position_plan"]

    output_path = tmp_path / "spot-plan.json"
    write_spot_planning_result(output_path, result)
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_spot_planning_input_rejects_non_object_json(tmp_path: Path) -> None:
    input_path = tmp_path / "invalid.json"
    input_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        load_spot_planning_input(input_path)
