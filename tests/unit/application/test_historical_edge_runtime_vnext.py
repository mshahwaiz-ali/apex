from __future__ import annotations

import hashlib
import json
from pathlib import Path

from apex.application.historical_edge_runtime import load_runtime_edge_artifact


def _write_artifact(path: Path, *, executed: int = 200) -> None:
    payload = {
        "dataset_hash": "dataset",
        "model_version": "apex-vnext-1",
        "profiles": [
            {
                "segment_key": "trend_pullback|long|*|*",
                "expected_r": 0.2,
                "fill_probability": 0.7,
                "probability_interval": [0.55, 0.75],
                "sample_size": 200,
            }
        ],
    }
    raw = json.dumps(payload, sort_keys=True).encode()
    path.write_bytes(raw)
    path.with_suffix(".json.manifest.json").write_text(
        json.dumps(
            {
                "artifact_sha256": hashlib.sha256(raw).hexdigest(),
                "promotion_metrics": {
                    "executed_outcomes": executed,
                    "segment_outcomes": 50,
                    "net_expectancy_r": 0.1,
                    "brier_skill": 0.01,
                    "calibration_error": 0.05,
                    "deflated_sharpe_probability": 0.95,
                    "probability_backtest_overfitting": 0.20,
                    "leakage_checks_passed": True,
                    "stability_checks_passed": True,
                    "artifact_integrity_passed": True,
                },
            }
        )
    )


def test_runtime_edge_loads_only_after_all_promotion_gates(tmp_path: Path) -> None:
    artifact_path = tmp_path / "runtime_edge.json"
    _write_artifact(artifact_path)
    artifact, reason = load_runtime_edge_artifact(artifact_path)
    assert artifact is not None
    assert reason == "historical edge available"

    _write_artifact(artifact_path, executed=199)
    withheld, reason = load_runtime_edge_artifact(artifact_path)
    assert withheld is None
    assert "fewer than 200" in reason
