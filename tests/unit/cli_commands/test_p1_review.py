from __future__ import annotations

import json
from pathlib import Path

import pytest

from apex.backtesting import EvidenceQuality
from apex.cli_commands.p1_review import (
    load_forward_edge_profile,
    load_historical_edge_profile,
)


DIMENSIONS = {
    "strategy": "trend_pullback",
    "direction": "LONG",
    "symbol": "BTCUSDT",
    "market_type": "futures",
}


def test_load_review_profiles(tmp_path: Path) -> None:
    historical_path = tmp_path / "historical.json"
    historical_path.write_text(
        json.dumps(
            {
                "dimensions": DIMENSIONS,
                "sample_size": 100,
                "win_rate": 0.6,
                "loss_rate": 0.4,
                "breakeven_rate": 0.0,
                "average_r": 0.5,
                "median_r": 0.4,
                "expectancy": 0.5,
                "profit_factor": 1.8,
                "maximum_drawdown_r": 3.0,
                "maximum_losing_streak": 4,
                "average_holding_candles": 8.0,
                "average_execution_cost_r": 0.05,
                "evidence_quality": EvidenceQuality.PROMISING.value,
            }
        ),
        encoding="utf-8",
    )
    forward_path = tmp_path / "forward.json"
    forward_path.write_text(
        json.dumps(
            {
                "dimensions": DIMENSIONS,
                "sample_size": 50,
                "win_rate": 0.56,
                "expectancy": 0.4,
                "profit_factor": 1.5,
                "maximum_drawdown_r": 3.5,
            }
        ),
        encoding="utf-8",
    )

    historical = load_historical_edge_profile(historical_path)
    forward = load_forward_edge_profile(forward_path)

    assert historical.dimensions == DIMENSIONS
    assert historical.evidence_quality is EvidenceQuality.PROMISING
    assert forward.dimensions == DIMENSIONS
    assert forward.sample_size == 50


def test_profile_loader_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError, match="JSON object"):
        load_forward_edge_profile(path)
