"""Leakage-safe queries and orchestration for persisted historical evidence."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from apex.application.historical_edge import (
    DatasetPartition,
    DatasetSplit,
    EvidenceThresholds,
    HistoricalDatasetMetadata,
    HistoricalEdgeMetrics,
    HistoricalOutcome,
    MarketType,
    aggregate_historical_edge,
)
from apex.application.historical_edge_io import (
    historical_edge_report_payload,
    write_historical_edge_report_sqlite,
)


@dataclass(frozen=True, slots=True)
class HistoricalEdgeQueryRequest:
    """One exact historical-evidence segment request.

    Final-test access is deliberately opt-in so normal calibration and validation
    workflows cannot consume the held-out partition accidentally.
    """

    market_type: MarketType
    strategy: str
    split: DatasetSplit
    symbol: str | None = None
    regime: str | None = None
    score_band: str | None = None
    dataset_id: str | None = None
    thresholds: EvidenceThresholds = field(default_factory=EvidenceThresholds)
    allow_final_test: bool = False

    def __post_init__(self) -> None:
        if not self.strategy.strip():
            raise ValueError("historical-edge strategy is required")
        if self.dataset_id is not None and not self.dataset_id.strip():
            raise ValueError("historical-edge dataset id cannot be blank")
        if self.split is DatasetSplit.TEST and not self.allow_final_test:
            raise ValueError("final TEST split access requires allow_final_test=True")


@dataclass(frozen=True, slots=True)
class HistoricalEdgeQueryResult:
    """Materialized outcomes, referenced datasets, metrics and report payload."""

    request: HistoricalEdgeQueryRequest
    outcomes: tuple[HistoricalOutcome, ...]
    datasets: tuple[HistoricalDatasetMetadata, ...]
    metrics: HistoricalEdgeMetrics
    report_payload: dict[str, Any]


def query_historical_outcomes_sqlite(
    path: Path,
    request: HistoricalEdgeQueryRequest,
) -> tuple[HistoricalOutcome, ...]:
    """Load one exact completed-outcome segment in chronological order."""

    if not path.exists():
        return ()
    clauses = ["market_type = ?", "strategy = ?", "split = ?"]
    parameters: list[object] = [
        request.market_type.value,
        request.strategy,
        request.split.value,
    ]
    for column, value in (
        ("symbol", request.symbol),
        ("regime", request.regime),
        ("score_band", request.score_band),
        ("dataset_id", request.dataset_id),
    ):
        if value is not None:
            clauses.append(f"{column} = ?")
            parameters.append(value)
    query = (
        "SELECT outcome_json FROM historical_outcomes WHERE "
        + " AND ".join(clauses)
        + " ORDER BY closed_at ASC, setup_id ASC"
    )
    with closing(sqlite3.connect(path)) as connection, connection:
        if not _table_exists(connection, "historical_outcomes"):
            return ()
        rows = connection.execute(query, tuple(parameters)).fetchall()
    return tuple(_outcome_from_json(row[0]) for row in rows)


def load_historical_datasets_sqlite(
    path: Path,
    *,
    market_type: MarketType | None = None,
    dataset_ids: Iterable[str] = (),
) -> tuple[HistoricalDatasetMetadata, ...]:
    """Load curated dataset metadata with deterministic ordering."""

    if not path.exists():
        return ()
    requested_ids = tuple(sorted(set(dataset_ids)))
    clauses: list[str] = []
    parameters: list[object] = []
    if market_type is not None:
        clauses.append("market_type = ?")
        parameters.append(market_type.value)
    if requested_ids:
        placeholders = ", ".join("?" for _ in requested_ids)
        clauses.append(f"dataset_id IN ({placeholders})")
        parameters.extend(requested_ids)
    where = "" if not clauses else " WHERE " + " AND ".join(clauses)
    query = (
        "SELECT metadata_json FROM historical_datasets"
        + where
        + " ORDER BY market_type ASC, dataset_id ASC"
    )
    with closing(sqlite3.connect(path)) as connection, connection:
        if not _table_exists(connection, "historical_datasets"):
            return ()
        rows = connection.execute(query, tuple(parameters)).fetchall()
    return tuple(_dataset_from_json(row[0]) for row in rows)


def run_historical_edge_query(
    path: Path,
    request: HistoricalEdgeQueryRequest,
    *,
    persist_report: bool = False,
) -> HistoricalEdgeQueryResult:
    """Build one reproducible report from an exact persisted segment."""

    outcomes = query_historical_outcomes_sqlite(path, request)
    metrics = aggregate_historical_edge(
        outcomes,
        market_type=request.market_type,
        strategy=request.strategy,
        split=request.split,
        symbol=request.symbol,
        regime=request.regime,
        score_band=request.score_band,
        thresholds=request.thresholds,
    )
    datasets = load_historical_datasets_sqlite(
        path,
        market_type=request.market_type,
        dataset_ids=metrics.dataset_ids,
    )
    found_ids = {item.dataset_id for item in datasets}
    missing_ids = sorted(set(metrics.dataset_ids) - found_ids)
    if missing_ids:
        raise ValueError("missing persisted dataset metadata: " + ", ".join(missing_ids))
    payload = historical_edge_report_payload(
        metrics,
        dataset_metadata=datasets,
    )
    if persist_report:
        write_historical_edge_report_sqlite(
            path,
            metrics,
            dataset_metadata=datasets,
        )
    return HistoricalEdgeQueryResult(
        request=request,
        outcomes=outcomes,
        datasets=datasets,
        metrics=metrics,
        report_payload=payload,
    )


def _outcome_from_json(raw: str) -> HistoricalOutcome:
    payload = _load_mapping(raw, "historical outcome")
    return HistoricalOutcome(
        setup_id=_required_string(payload, "setup_id"),
        dataset_id=_required_string(payload, "dataset_id"),
        split=DatasetSplit(_required_string(payload, "split")),
        market_type=MarketType(_required_string(payload, "market_type")),
        strategy=_required_string(payload, "strategy"),
        symbol=_required_string(payload, "symbol"),
        regime=_required_string(payload, "regime"),
        score_band=_required_string(payload, "score_band"),
        opened_at=_aware_datetime(payload, "opened_at"),
        closed_at=_aware_datetime(payload, "closed_at"),
        net_return=float(payload["net_return"]),
        r_multiple=float(payload["r_multiple"]),
        maximum_favorable_excursion_r=float(payload["maximum_favorable_excursion_r"]),
        maximum_adverse_excursion_r=float(payload["maximum_adverse_excursion_r"]),
        won=bool(payload["won"]),
    )


def _dataset_from_json(raw: str) -> HistoricalDatasetMetadata:
    payload = _load_mapping(raw, "historical dataset")
    raw_partitions = payload.get("partitions")
    if not isinstance(raw_partitions, list):
        raise ValueError("historical dataset partitions must be a list")
    partitions = tuple(_partition_from_payload(item) for item in raw_partitions)
    symbols = payload.get("symbols")
    timeframes = payload.get("timeframes")
    if not isinstance(symbols, list) or not all(isinstance(item, str) for item in symbols):
        raise ValueError("historical dataset symbols must be strings")
    if not isinstance(timeframes, list) or not all(isinstance(item, str) for item in timeframes):
        raise ValueError("historical dataset timeframes must be strings")
    return HistoricalDatasetMetadata(
        dataset_id=_required_string(payload, "dataset_id"),
        market_type=MarketType(_required_string(payload, "market_type")),
        symbols=tuple(symbols),
        timeframes=tuple(timeframes),
        source=_required_string(payload, "source"),
        first_observation_at=_aware_datetime(payload, "first_observation_at"),
        last_observation_at=_aware_datetime(payload, "last_observation_at"),
        observation_count=int(payload["observation_count"]),
        partitions=partitions,
        content_hash=_required_string(payload, "content_hash"),
    )


def _partition_from_payload(value: object) -> DatasetPartition:
    if not isinstance(value, dict):
        raise ValueError("historical dataset partition must be a mapping")
    return DatasetPartition(
        split=DatasetSplit(_required_string(value, "split")),
        start_at=_aware_datetime(value, "start_at"),
        end_at=_aware_datetime(value, "end_at"),
    )


def _load_mapping(raw: str, label: str) -> dict[str, Any]:
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ValueError(f"stored {label} must contain a JSON object")
    return loaded


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"stored payload requires {key}")
    return value


def _aware_datetime(payload: dict[str, Any], key: str) -> datetime:
    value = _required_string(payload, key)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"stored {key} must be timezone-aware")
    return parsed


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None
