from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apex.application.historical_dataset_io import (
    load_curated_dataset_manifest_sqlite,
    load_historical_outcome_import_sqlite,
    write_curated_dataset_manifest_sqlite,
    write_historical_outcome_import_sqlite,
)
from apex.application.historical_dataset_manifest import (
    DatasetValidationState,
    build_curated_dataset_manifest,
)
from apex.application.historical_edge import DatasetPartition, DatasetSplit, MarketType
from apex.application.historical_outcome_conversion import convert_backtest_trades
from apex.backtesting import BacktestOutcome, BacktestSignal, SimulatedTrade
from apex.strategies import StrategyType, TradeDirection

_START = datetime(2026, 1, 1, tzinfo=UTC)
_PARTITIONS = (
    DatasetPartition(DatasetSplit.TRAIN, _START, _START + timedelta(minutes=10)),
    DatasetPartition(
        DatasetSplit.VALIDATION,
        _START + timedelta(minutes=10),
        _START + timedelta(minutes=20),
    ),
    DatasetPartition(
        DatasetSplit.TEST,
        _START + timedelta(minutes=20),
        _START + timedelta(minutes=30),
    ),
)


def _records() -> list[dict[str, object]]:
    return [
        {
            "symbol": "BTC/USDT",
            "timeframe": "5m",
            "open_time": _START + timedelta(minutes=5 * index),
            "close_time": _START + timedelta(minutes=5 * (index + 1)),
            "open": 100.0 + index,
            "high": 102.0 + index,
            "low": 99.0 + index,
            "close": 101.0 + index,
            "volume": 1000.0,
        }
        for index in range(6)
    ]


def _summary():
    entry_time = _START + timedelta(minutes=5)
    signal = BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=_START,
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=10.0,
        risk_amount=20.0,
        confidence_score=80.0,
    )
    trade = SimulatedTrade(
        signal=signal,
        outcome=BacktestOutcome.TARGET,
        exit_time=_START + timedelta(minutes=9),
        exit_price=104.0,
        gross_pnl=40.0,
        fees=1.0,
        net_pnl=39.0,
        realized_r_multiple=1.95,
        holding_candles=2,
        metadata={
            "entry_time": entry_time.isoformat(),
            "executed_entry_price": 100.0,
            "regime": "TREND",
            "maximum_favorable_excursion_r": 2.0,
            "maximum_adverse_excursion_r": -0.25,
        },
    )
    return convert_backtest_trades(
        (trade,),
        dataset_id="dataset-001",
        market_type=MarketType.FUTURES,
        partitions=_PARTITIONS,
        source_identity="campaign-001/run-001",
    )


def test_manifest_round_trip_and_idempotent_upsert(tmp_path: Path) -> None:
    built = build_curated_dataset_manifest(
        dataset_id="dataset-001",
        market_type=MarketType.FUTURES,
        source_type="json",
        source_identifier="fixtures/btc.json",
        exchange_provider="fixture",
        records=_records(),
        expected_interval="5m",
        partitions=_PARTITIONS,
        created_at=_START,
        expected_symbols=("BTC/USDT",),
        expected_timeframes=("5m",),
    )
    assert built.manifest is not None
    database = tmp_path / "historical-edge.sqlite3"

    write_curated_dataset_manifest_sqlite(
        database,
        built.manifest,
        validation_state=built.validation.state.value,
    )
    write_curated_dataset_manifest_sqlite(
        database,
        built.manifest,
        validation_state=built.validation.state.value,
    )

    loaded = load_curated_dataset_manifest_sqlite(database, "dataset-001")
    assert loaded is not None
    assert loaded["content_hash"] == built.manifest.content_hash
    assert loaded["market_type"] == MarketType.FUTURES.value
    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM historical_dataset_manifests").fetchone()
        version = connection.execute(
            "SELECT value FROM historical_edge_metadata WHERE key = 'schema_version'"
        ).fetchone()
    assert count == (1,)
    assert version == ("2",)


def test_outcome_import_round_trip_is_atomic_and_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "historical-edge.sqlite3"
    summary = _summary()

    assert write_historical_outcome_import_sqlite(database, summary) == 1
    assert write_historical_outcome_import_sqlite(database, summary) == 1

    loaded = load_historical_outcome_import_sqlite(database, summary.result_hash)
    assert loaded is not None
    assert loaded["accepted_count"] == 1
    assert loaded["dataset_id"] == "dataset-001"
    with sqlite3.connect(database) as connection:
        import_count = connection.execute(
            "SELECT COUNT(*) FROM historical_outcome_imports"
        ).fetchone()
        outcome_count = connection.execute("SELECT COUNT(*) FROM historical_outcomes").fetchone()
    assert import_count == (1,)
    assert outcome_count == (1,)


def test_missing_persistence_rows_return_none(tmp_path: Path) -> None:
    database = tmp_path / "missing.sqlite3"

    assert load_curated_dataset_manifest_sqlite(database, "missing") is None
    assert load_historical_outcome_import_sqlite(database, "0" * 64) is None
    assert not database.exists()


def test_manifest_warning_state_is_persisted(tmp_path: Path) -> None:
    records = _records()
    del records[2]
    built = build_curated_dataset_manifest(
        dataset_id="dataset-warning",
        market_type=MarketType.FUTURES,
        source_type="json",
        source_identifier="fixtures/gapped.json",
        exchange_provider="fixture",
        records=records,
        expected_interval="5m",
        partitions=(),
        created_at=_START,
    )
    assert built.validation.state is DatasetValidationState.VALID_WITH_WARNINGS
    assert built.manifest is not None
    database = tmp_path / "historical-edge.sqlite3"

    write_curated_dataset_manifest_sqlite(
        database,
        built.manifest,
        validation_state=built.validation.state.value,
    )

    with sqlite3.connect(database) as connection:
        state = connection.execute(
            "SELECT validation_state FROM historical_dataset_manifests WHERE dataset_id = ?",
            (built.manifest.dataset_id,),
        ).fetchone()
    assert state == (DatasetValidationState.VALID_WITH_WARNINGS.value,)
