"""Versioned, leakage-aware research experiment manifests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from apex.application.methodology_identity import METHODOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class ExperimentManifest:
    schema_version: int
    experiment_id: str
    methodology_version: str
    dataset_fingerprint: str
    symbols: tuple[str, ...]
    behavioral_cohorts: tuple[str, ...]
    timeframes: tuple[str, ...]
    validation_method: str
    final_test_untouched: bool
    purge_horizon_bars: int
    embargo_bars: int
    attempted_configurations: int
    cost_profile: str
    promotion_objective: str

    def __post_init__(self) -> None:
        for name, value in (
            ("experiment id", self.experiment_id),
            ("methodology version", self.methodology_version),
            ("dataset fingerprint", self.dataset_fingerprint),
            ("validation method", self.validation_method),
            ("cost profile", self.cost_profile),
            ("promotion objective", self.promotion_objective),
        ):
            if not value.strip():
                raise ValueError(f"{name} cannot be empty")
        if self.schema_version < 1:
            raise ValueError("experiment schema version must be positive")
        if self.purge_horizon_bars < 0 or self.embargo_bars < 0:
            raise ValueError("purge and embargo bars cannot be negative")
        if self.attempted_configurations < 1:
            raise ValueError("attempted configurations must be positive")

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def as_payload(self) -> dict[str, Any]:
        return {**asdict(self), "fingerprint": self.fingerprint}


def default_experiment_manifest(
    *,
    dataset_fingerprint: str,
    symbols: tuple[str, ...],
    experiment_id: str = "canonical-walk-forward",
) -> ExperimentManifest:
    return ExperimentManifest(
        schema_version=1,
        experiment_id=experiment_id,
        methodology_version=METHODOLOGY_VERSION,
        dataset_fingerprint=dataset_fingerprint,
        symbols=symbols,
        behavioral_cohorts=(
            "insufficient_history",
            "high_wick",
            "extreme_volatility",
            "directional",
            "range_or_chop",
            "mixed",
        ),
        timeframes=("1m", "3m", "5m", "15m", "30m", "1h", "4h"),
        validation_method="expanding_walk_forward_with_purge_embargo",
        final_test_untouched=True,
        purge_horizon_bars=24,
        embargo_bars=24,
        attempted_configurations=1,
        cost_profile="conservative_market",
        promotion_objective="balanced_edge",
    )


def load_experiment_manifest(path: Path) -> ExperimentManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("experiment manifest root must be an object")
    for name in ("symbols", "behavioral_cohorts", "timeframes"):
        if name in payload:
            payload[name] = tuple(payload[name])
    payload.pop("fingerprint", None)
    return ExperimentManifest(**payload)


def write_experiment_manifest(path: Path, manifest: ExperimentManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.as_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "ExperimentManifest",
    "default_experiment_manifest",
    "load_experiment_manifest",
    "write_experiment_manifest",
]
