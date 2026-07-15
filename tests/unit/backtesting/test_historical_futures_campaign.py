"""Focused contract tests for deterministic historical futures campaigns."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from apex.backtesting import (
    BacktestConfig,
    HistoricalFuturesCampaignRequest,
    HistoricalFuturesExecutionManifest,
    load_historical_futures_execution_manifest,
)

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _request(tmp_path: Path, **overrides: object) -> HistoricalFuturesCampaignRequest:
    values: dict[str, object] = {
        "campaign_id": "campaign-1",
        "records_path": tmp_path / "signals.jsonl",
        "signal_manifest_path": tmp_path / "signals-manifest.json",
        "result_path": tmp_path / "result.json",
        "execution_manifest_path": tmp_path / "execution.json",
        "starting_equity": 10_000.0,
        "backtest_config": BacktestConfig(),
    }
    values.update(overrides)
    return HistoricalFuturesCampaignRequest(
        campaign_id=cast(str, values["campaign_id"]),
        records_path=cast(Path, values["records_path"]),
        signal_manifest_path=cast(Path, values["signal_manifest_path"]),
        result_path=cast(Path, values["result_path"]),
        execution_manifest_path=cast(Path, values["execution_manifest_path"]),
        starting_equity=cast(float, values["starting_equity"]),
        backtest_config=cast(BacktestConfig, values["backtest_config"]),
    )


def test_request_accepts_unique_paths_and_positive_equity(tmp_path: Path) -> None:
    request = _request(tmp_path)

    assert request.campaign_id == "campaign-1"
    assert request.starting_equity == 10_000.0
    assert request.backtest_config.conservative_intrabar is True


@pytest.mark.parametrize("starting_equity", [0.0, -1.0, float("inf"), float("nan")])
def test_request_rejects_invalid_starting_equity(
    tmp_path: Path,
    starting_equity: float,
) -> None:
    with pytest.raises(ValueError, match="starting equity"):
        _request(tmp_path, starting_equity=starting_equity)


def test_request_rejects_duplicate_paths(tmp_path: Path) -> None:
    duplicate = tmp_path / "same.json"

    with pytest.raises(ValueError, match="paths must be unique"):
        _request(
            tmp_path,
            result_path=duplicate,
            execution_manifest_path=duplicate,
        )


def test_execution_manifest_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "execution.json"
    manifest = HistoricalFuturesExecutionManifest(
        campaign_id="campaign-1",
        signal_records_hash=_SHA_A,
        signal_configuration_hash=_SHA_B,
        result_path="result.json",
        result_hash=_SHA_C,
        total_decisions=6,
        trade_count=2,
        split_counts=(("final_test", 2), ("train", 2), ("validation", 2)),
    )
    path.write_text(
        json.dumps(manifest.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    assert load_historical_futures_execution_manifest(path) == manifest


def test_execution_manifest_rejects_invalid_hash(tmp_path: Path) -> None:
    path = tmp_path / "execution.json"
    payload = HistoricalFuturesExecutionManifest(
        campaign_id="campaign-1",
        signal_records_hash=_SHA_A,
        signal_configuration_hash=_SHA_B,
        result_path="result.json",
        result_hash=_SHA_C,
        total_decisions=3,
        trade_count=1,
        split_counts=(("final_test", 1), ("train", 1), ("validation", 1)),
    ).to_payload()
    payload["result_hash"] = "invalid"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        load_historical_futures_execution_manifest(path)


def test_execution_manifest_rejects_split_count_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "execution.json"
    payload = HistoricalFuturesExecutionManifest(
        campaign_id="campaign-1",
        signal_records_hash=_SHA_A,
        signal_configuration_hash=_SHA_B,
        result_path="result.json",
        result_hash=_SHA_C,
        total_decisions=3,
        trade_count=1,
        split_counts=(("final_test", 1), ("train", 1), ("validation", 1)),
    ).to_payload()
    payload["split_counts"] = {"train": 1}
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="split counts"):
        load_historical_futures_execution_manifest(path)
