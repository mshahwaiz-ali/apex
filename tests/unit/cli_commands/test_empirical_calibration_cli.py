from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from apex.cli_app import app
from apex.optimization import load_and_verify_empirical_calibration_report


def _performance(expectancy: float, drawdown: float) -> dict[str, object]:
    return {
        "metrics": {
            "total_trades": 20,
            "win_rate": 0.60,
            "expectancy": expectancy,
            "profit_factor": 1.50,
            "maximum_drawdown": drawdown,
            "net_profit": expectancy * 20,
            "by_symbol": {"BTCUSDT": 10, "ETHUSDT": 10},
            "by_strategy": {"trend_pullback": 20},
            "by_regime": {"risk_on": 12, "range": 8},
            "by_score_band": {"70-79": 8, "80-89": 12},
        }
    }


def test_empirical_calibration_cli_persists_verified_report(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "report.json"
    payload = {
        "split": {
            "train_start": "2025-01-01",
            "train_end": "2025-06-30",
            "validation_start": "2025-07-01",
            "validation_end": "2025-09-30",
            "out_of_sample_start": "2025-10-01",
            "out_of_sample_end": "2025-12-31",
        },
        "run_config": {
            "identifier": "s10-cli",
            "variable_group": "scoring_thresholds",
            "minimum_trades": 10,
            "minimum_expectancy_delta": 0.05,
            "maximum_drawdown_increase_pct": 0.0,
        },
        "parameter_set": {
            "identifier": "candidate-a",
            "group": "scoring_thresholds",
            "parameters": {"trend_pullback_minimum_score": 76},
        },
        "train_baseline": _performance(0.20, 0.10),
        "train_candidate": _performance(0.30, 0.09),
        "validation_baseline": _performance(0.15, 0.12),
        "validation_candidate": _performance(0.25, 0.10),
        "final_test_baseline": _performance(0.10, 0.11),
        "final_test_candidate": _performance(0.18, 0.10),
    }
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "optimize",
            "empirical-calibrate",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EMPIRICAL_CALIBRATION_COMPLETED" in result.output
    assert "selected=True" in result.output
    verified = load_and_verify_empirical_calibration_report(output_path)
    assert verified.payload["selected_for_final_test_audit"] is True
    assert verified.payload["final_test_audit"]["used_for_selection"] is False
