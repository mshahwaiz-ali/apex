from __future__ import annotations

from pathlib import Path

from apex.research.experiment import (
    default_experiment_manifest,
    load_experiment_manifest,
    write_experiment_manifest,
)


def test_experiment_manifest_round_trip_is_versioned_and_stable(tmp_path: Path) -> None:
    manifest = default_experiment_manifest(
        dataset_fingerprint="a" * 64,
        symbols=("BTCUSDT", "ETHUSDT"),
    )
    path = tmp_path / "experiment.json"

    write_experiment_manifest(path, manifest)
    loaded = load_experiment_manifest(path)

    assert loaded == manifest
    assert loaded.final_test_untouched is True
    assert loaded.cost_profile == "conservative_market"
    assert loaded.fingerprint == manifest.fingerprint
