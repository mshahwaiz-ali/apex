"""Persistence verification for deterministic historical spot backtests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from apex.application.spot_historical_backtest import (
    SpotHistoricalBacktestManifest,
    SpotHistoricalBacktestResult,
)


def load_and_verify_spot_historical_backtest(
    *,
    result_path: Path,
    manifest_path: Path,
) -> SpotHistoricalBacktestResult:
    """Reload persisted artifacts and verify their deterministic integrity binding."""

    payload = _load_object(result_path)
    manifest = SpotHistoricalBacktestManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )

    result_hash = payload.get("result_sha256")
    if not isinstance(result_hash, str) or not result_hash:
        raise ValueError("historical spot backtest result hash is missing")

    hashable_payload = dict(payload)
    hashable_payload.pop("result_sha256", None)
    if _hash_payload(hashable_payload) != result_hash:
        raise ValueError("historical spot backtest result hash does not match its payload")
    if manifest.result_sha256 != result_hash:
        raise ValueError("historical spot backtest manifest references a different result")

    expected_fields: dict[str, object] = {
        "campaign_id": manifest.campaign_id,
        "source_dataset_sha256": manifest.source_dataset_sha256,
        "replay_records_sha256": manifest.replay_records_sha256,
        "replay_configuration_sha256": manifest.replay_configuration_sha256,
        "backtest_configuration_sha256": manifest.backtest_configuration_sha256,
    }
    for field, expected in expected_fields.items():
        if payload.get(field) != expected:
            raise ValueError(
                f"historical spot backtest manifest mismatch for field: {field}"
            )

    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping):
        raise TypeError("historical spot backtest metrics must be an object")
    count_fields = {
        "signal_count": manifest.signal_count,
        "eligible_count": manifest.eligible_count,
        "plan_count": manifest.plan_count,
        "fill_count": manifest.fill_count,
        "trade_count": manifest.trade_count,
    }
    for field, expected in count_fields.items():
        if metrics.get(field, 0) != expected:
            raise ValueError(
                f"historical spot backtest manifest mismatch for metric: {field}"
            )
    if metrics.get("ending_equity") != manifest.ending_equity:
        raise ValueError(
            "historical spot backtest manifest mismatch for metric: ending_equity"
        )

    return SpotHistoricalBacktestResult(manifest=manifest, payload=payload)


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON artifact must contain an object: {path}")
    if not all(isinstance(key, str) for key in value):
        raise TypeError(f"JSON artifact object keys must be strings: {path}")
    return cast(dict[str, Any], value)


def _hash_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
