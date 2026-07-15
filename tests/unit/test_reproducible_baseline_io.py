"""Focused tests for reproducible baseline dataset and report workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TypedDict, cast

import pytest

from apex.application.backtest_comparison import compare_backtest_reports
from apex.application.backtest_report_io import (
    BACKTEST_CAMPAIGN_DB_SCHEMA_VERSION,
    BACKTEST_REPORT_DB_SCHEMA_VERSION,
    dumps_report,
    list_backtest_campaign_metadata_sqlite,
    list_backtest_report_metadata_sqlite,
    load_backtest_campaign_sqlite,
    load_backtest_report_sqlite,
    make_run_id,
    to_json_value,
    write_backtest_campaign_sqlite,
    write_backtest_report,
    write_backtest_report_sqlite,
)
from apex.application.historical_dataset import load_historical_candles
from apex.application.historical_dataset_export import build_dataset_payload, write_dataset
from apex.domain.models import Candle


class _Direction(Enum):
    LONG = "LONG"


@dataclass(frozen=True)
class _Example:
    at: datetime
    direction: _Direction


class _RunIdentityKwargs(TypedDict):
    symbol: str
    replay_timeframe: str
    dataset_hash: str
    config_hash: str


def _candle(minute: int, *, closed: bool = True, timeframe: str = "5m") -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute)
    return Candle(
        symbol="BTCUSDT",
        timeframe=timeframe,
        open_time=opened,
        close_time=opened + timedelta(minutes=5),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1000.0,
        is_closed=closed,
        source="fixture",
    )


def test_dataset_export_filters_and_orders_closed_candles(tmp_path: Path) -> None:
    payload = build_dataset_payload(
        symbol="BTCUSDT",
        candles_by_timeframe={"5m": (_candle(10), _candle(5), _candle(15, closed=False))},
        source="fixture",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert payload["schema_version"] == 1
    assert payload["symbol"] == "BTC/USDT"
    candle_rows = cast(list[dict[str, object]], payload["candles"])
    assert [row["open_time"] for row in candle_rows] == [
        _candle(5).open_time.isoformat(),
        _candle(10).open_time.isoformat(),
    ]

    path = tmp_path / "dataset.json"
    write_dataset(path, payload)
    loaded = load_historical_candles(
        path,
        expected_symbol="BTCUSDT",
        required_timeframes=("5m",),
    )
    assert len(loaded["5m"]) == 2
    with pytest.raises(ValueError, match="refusing to overwrite"):
        write_dataset(path, payload)


def test_dataset_loader_rejects_unknown_schema_version(tmp_path: Path) -> None:
    payload = build_dataset_payload(
        symbol="BTCUSDT",
        candles_by_timeframe={"5m": (_candle(0),)},
        source="fixture",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    payload["schema_version"] = 999
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported historical dataset schema_version"):
        load_historical_candles(path)


def test_report_serialization_is_explicit_and_stable(tmp_path: Path) -> None:
    value = _Example(datetime(2026, 1, 1, tzinfo=UTC), _Direction.LONG)
    assert to_json_value(value) == {
        "at": "2026-01-01T00:00:00+00:00",
        "direction": "LONG",
    }
    assert dumps_report({"example": value}) == dumps_report({"example": value})

    path = tmp_path / "report.json"
    write_backtest_report(path, {"example": value})
    with pytest.raises(ValueError, match="refusing to overwrite"):
        write_backtest_report(path, {"example": value})


def test_run_identity_is_stable() -> None:
    kwargs: _RunIdentityKwargs = {
        "symbol": "BTC/USDT",
        "replay_timeframe": "5m",
        "dataset_hash": "a" * 64,
        "config_hash": "b" * 64,
    }
    assert make_run_id(**kwargs) == "btc-usdt-5m-aaaaaaaaaaaa-bbbbbbbbbbbb"
    assert make_run_id(**kwargs) == make_run_id(**kwargs)


def test_backtest_report_comparison(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    base = {
        "metadata": {"dataset_hash": "a" * 64, "config_hash": "b" * 64},
        "metrics": {
            "trade_count": 2,
            "net_profit": 10.0,
            "expectancy": 5.0,
            "profit_factor": 1.5,
            "maximum_drawdown": 2.0,
            "win_rate": 0.5,
        },
    }
    write_backtest_report(left, base)
    changed = json.loads(json.dumps(base))
    changed["metrics"]["net_profit"] = 15.0
    write_backtest_report(right, changed)

    comparison = compare_backtest_reports(left, right)
    assert comparison["dataset_hash"]["matches"] is True
    assert comparison["config_hash"]["matches"] is True
    assert comparison["metrics"]["net_profit"]["delta"] == 5.0


def test_backtest_report_sqlite_upserts_and_loads_report(tmp_path: Path) -> None:
    path = tmp_path / "backtests.db"
    payload = {
        "symbol": "BTC/USDT",
        "dataset_source": "fixture",
        "metadata": {
            "run_id": "btc-usdt-5m-aaaaaaaaaaaa-bbbbbbbbbbbb",
            "dataset_hash": "a" * 64,
            "config_hash": "b" * 64,
            "replay_timeframe": "5m",
        },
        "metrics": {
            "total_trades": 2,
            "net_profit": 10.0,
            "maximum_drawdown": 2.0,
        },
        "trades": [],
    }

    write_backtest_report_sqlite(path, payload)
    write_backtest_report_sqlite(path, payload)

    loaded = load_backtest_report_sqlite(path, "btc-usdt-5m-aaaaaaaaaaaa-bbbbbbbbbbbb")
    assert loaded == payload
    metadata = list_backtest_report_metadata_sqlite(path)
    assert len(metadata) == 1
    assert metadata[0]["schema_version"] == BACKTEST_REPORT_DB_SCHEMA_VERSION
    assert metadata[0]["run_id"] == "btc-usdt-5m-aaaaaaaaaaaa-bbbbbbbbbbbb"
    assert metadata[0]["symbol"] == "BTC/USDT"
    assert metadata[0]["total_trades"] == 2


def test_backtest_report_sqlite_helpers_handle_missing_database(tmp_path: Path) -> None:
    path = tmp_path / "missing.db"

    assert load_backtest_report_sqlite(path, "missing") is None
    assert list_backtest_report_metadata_sqlite(path) == ()


def test_backtest_campaign_sqlite_upserts_and_loads_campaign(tmp_path: Path) -> None:
    path = tmp_path / "campaigns.db"
    payload = {
        "schema_version": 1,
        "campaign_id": "btc-usdt-campaign-abc",
        "symbol": "BTC/USDT",
        "dataset_source": "fixture",
        "variant_count": 2,
        "best_variant_id": "candidate",
        "rankings": [
            {
                "rank": 1,
                "variant_id": "candidate",
                "run_id": "candidate-run",
                "total_trades": 3,
                "net_profit": 12.5,
                "expectancy": 4.1,
                "maximum_drawdown": 1.0,
                "failure_count": 0,
            }
        ],
        "variants": [],
    }

    write_backtest_campaign_sqlite(path, payload)
    write_backtest_campaign_sqlite(path, payload)

    loaded = load_backtest_campaign_sqlite(path, "btc-usdt-campaign-abc")
    assert loaded == payload
    metadata = list_backtest_campaign_metadata_sqlite(path)
    assert len(metadata) == 1
    assert metadata[0]["schema_version"] == BACKTEST_CAMPAIGN_DB_SCHEMA_VERSION
    assert metadata[0]["campaign_id"] == "btc-usdt-campaign-abc"
    assert metadata[0]["best_variant_id"] == "candidate"
    assert metadata[0]["best_net_profit"] == 12.5
