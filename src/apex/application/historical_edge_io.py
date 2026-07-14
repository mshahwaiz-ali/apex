"""Deterministic report serialization and SQLite storage for historical edge."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from apex.application.backtest_report_io import dumps_report, to_json_value
from apex.application.historical_edge import (
    DatasetPartition,
    HistoricalDatasetMetadata,
    HistoricalEdgeMetrics,
    HistoricalOutcome,
)

HISTORICAL_EDGE_DB_SCHEMA_VERSION = 1
HISTORICAL_EDGE_REPORT_SCHEMA_VERSION = 1


def historical_edge_report_payload(
    metrics: HistoricalEdgeMetrics,
    *,
    dataset_metadata: Iterable[HistoricalDatasetMetadata] = (),
) -> dict[str, Any]:
    """Build one deterministic, self-contained historical-edge report payload."""

    datasets = tuple(
        sorted(dataset_metadata, key=lambda item: (item.market_type.value, item.dataset_id))
    )
    referenced_ids = set(metrics.dataset_ids)
    included = tuple(item for item in datasets if item.dataset_id in referenced_ids)
    if {item.dataset_id for item in included} != referenced_ids:
        missing = sorted(referenced_ids - {item.dataset_id for item in included})
        raise ValueError(f"missing dataset metadata for report: {', '.join(missing)}")
    return {
        "schema_version": HISTORICAL_EDGE_REPORT_SCHEMA_VERSION,
        "result_hash": metrics.result_hash,
        "market_type": metrics.market_type.value,
        "strategy": metrics.strategy,
        "split": metrics.split.value,
        "segment": {
            "symbol": metrics.symbol,
            "regime": metrics.regime,
            "score_band": metrics.score_band,
        },
        "evidence": {
            "quality": metrics.evidence_quality.value,
            "insufficient_reason": metrics.insufficient_reason,
            "sample_count": metrics.sample_count,
            "wins": metrics.wins,
            "losses": metrics.losses,
        },
        "metrics": {
            "win_rate": metrics.win_rate,
            "expectancy_r": metrics.expectancy_r,
            "average_win_r": metrics.average_win_r,
            "average_loss_r": metrics.average_loss_r,
            "profit_factor": metrics.profit_factor,
            "average_mfe_r": metrics.average_mfe_r,
            "average_mae_r": metrics.average_mae_r,
        },
        "dataset_ids": list(metrics.dataset_ids),
        "datasets": [_dataset_payload(item) for item in included],
    }


def dumps_historical_edge_report(
    metrics: HistoricalEdgeMetrics,
    *,
    dataset_metadata: Iterable[HistoricalDatasetMetadata] = (),
) -> str:
    """Serialize one historical-edge report deterministically."""

    return dumps_report(historical_edge_report_payload(metrics, dataset_metadata=dataset_metadata))


def write_historical_edge_report(
    path: Path,
    metrics: HistoricalEdgeMetrics,
    *,
    dataset_metadata: Iterable[HistoricalDatasetMetadata] = (),
    force: bool = False,
) -> None:
    """Atomically write one historical-edge JSON report."""

    if path.exists() and not force:
        raise ValueError(f"refusing to overwrite existing report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        dumps_historical_edge_report(metrics, dataset_metadata=dataset_metadata),
        encoding="utf-8",
    )
    temporary.replace(path)


def write_historical_dataset_sqlite(path: Path, metadata: HistoricalDatasetMetadata) -> None:
    """Upsert one curated dataset identity and split definition."""

    payload = _dataset_payload(metadata)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO historical_datasets (
                dataset_id, market_type, source, first_observation_at,
                last_observation_at, observation_count, content_hash, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id) DO UPDATE SET
                market_type=excluded.market_type,
                source=excluded.source,
                first_observation_at=excluded.first_observation_at,
                last_observation_at=excluded.last_observation_at,
                observation_count=excluded.observation_count,
                content_hash=excluded.content_hash,
                metadata_json=excluded.metadata_json
            """,
            (
                metadata.dataset_id,
                metadata.market_type.value,
                metadata.source,
                metadata.first_observation_at.isoformat(),
                metadata.last_observation_at.isoformat(),
                metadata.observation_count,
                metadata.content_hash,
                dumps_report(payload),
            ),
        )


def write_historical_outcomes_sqlite(path: Path, outcomes: Iterable[HistoricalOutcome]) -> int:
    """Upsert completed chronological outcomes and return the written row count."""

    materialized = tuple(outcomes)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_schema(connection)
        for outcome in materialized:
            connection.execute(
                """
                INSERT INTO historical_outcomes (
                    setup_id, dataset_id, split, market_type, strategy, symbol,
                    regime, score_band, opened_at, closed_at, outcome_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(setup_id) DO UPDATE SET
                    dataset_id=excluded.dataset_id,
                    split=excluded.split,
                    market_type=excluded.market_type,
                    strategy=excluded.strategy,
                    symbol=excluded.symbol,
                    regime=excluded.regime,
                    score_band=excluded.score_band,
                    opened_at=excluded.opened_at,
                    closed_at=excluded.closed_at,
                    outcome_json=excluded.outcome_json
                """,
                (
                    outcome.setup_id,
                    outcome.dataset_id,
                    outcome.split.value,
                    outcome.market_type.value,
                    outcome.strategy,
                    outcome.symbol,
                    outcome.regime,
                    outcome.score_band,
                    outcome.opened_at.isoformat(),
                    outcome.closed_at.isoformat(),
                    dumps_report(_outcome_payload(outcome)),
                ),
            )
    return len(materialized)


def write_historical_edge_report_sqlite(
    path: Path,
    metrics: HistoricalEdgeMetrics,
    *,
    dataset_metadata: Iterable[HistoricalDatasetMetadata] = (),
) -> None:
    """Upsert one aggregate report keyed by its deterministic result hash."""

    payload = historical_edge_report_payload(metrics, dataset_metadata=dataset_metadata)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO historical_edge_reports (
                result_hash, market_type, strategy, split, symbol, regime,
                score_band, evidence_quality, sample_count, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(result_hash) DO UPDATE SET
                market_type=excluded.market_type,
                strategy=excluded.strategy,
                split=excluded.split,
                symbol=excluded.symbol,
                regime=excluded.regime,
                score_band=excluded.score_band,
                evidence_quality=excluded.evidence_quality,
                sample_count=excluded.sample_count,
                report_json=excluded.report_json
            """,
            (
                metrics.result_hash,
                metrics.market_type.value,
                metrics.strategy,
                metrics.split.value,
                metrics.symbol,
                metrics.regime,
                metrics.score_band,
                metrics.evidence_quality.value,
                metrics.sample_count,
                dumps_report(payload),
            ),
        )


def load_historical_edge_report_sqlite(path: Path, result_hash: str) -> dict[str, Any] | None:
    """Load one aggregate report by deterministic result hash."""

    if not path.exists():
        return None
    with sqlite3.connect(path) as connection:
        _ensure_schema(connection)
        row = connection.execute(
            "SELECT report_json FROM historical_edge_reports WHERE result_hash = ?",
            (result_hash,),
        ).fetchone()
    if row is None:
        return None
    loaded = json.loads(row[0])
    if not isinstance(loaded, dict):
        raise ValueError("stored historical-edge report must be a JSON object")
    return loaded


def list_historical_edge_report_metadata_sqlite(
    path: Path, *, limit: int = 100
) -> tuple[dict[str, Any], ...]:
    """List aggregate report metadata without loading full report payloads."""

    if limit <= 0:
        raise ValueError("historical-edge report metadata limit must be positive")
    if not path.exists():
        return ()
    with sqlite3.connect(path) as connection:
        _ensure_schema(connection)
        rows = connection.execute(
            """
            SELECT result_hash, market_type, strategy, split, symbol, regime,
                   score_band, evidence_quality, sample_count
            FROM historical_edge_reports
            ORDER BY market_type, strategy, split, result_hash
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return tuple(
        {
            "result_hash": row[0],
            "market_type": row[1],
            "strategy": row[2],
            "split": row[3],
            "symbol": row[4],
            "regime": row[5],
            "score_band": row[6],
            "evidence_quality": row[7],
            "sample_count": row[8],
        }
        for row in rows
    )


def _dataset_payload(metadata: HistoricalDatasetMetadata) -> dict[str, Any]:
    return {
        "dataset_id": metadata.dataset_id,
        "market_type": metadata.market_type.value,
        "symbols": list(metadata.symbols),
        "timeframes": list(metadata.timeframes),
        "source": metadata.source,
        "first_observation_at": metadata.first_observation_at.isoformat(),
        "last_observation_at": metadata.last_observation_at.isoformat(),
        "observation_count": metadata.observation_count,
        "partitions": [_partition_payload(item) for item in metadata.partitions],
        "content_hash": metadata.content_hash,
    }


def _partition_payload(partition: DatasetPartition) -> dict[str, Any]:
    return {
        "split": partition.split.value,
        "start_at": partition.start_at.isoformat(),
        "end_at": partition.end_at.isoformat(),
    }


def _outcome_payload(outcome: HistoricalOutcome) -> dict[str, Any]:
    normalized = to_json_value(outcome)
    if not isinstance(normalized, dict):
        raise TypeError("historical outcome did not serialize to a mapping")
    return normalized


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS historical_edge_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO historical_edge_metadata (key, value)
        VALUES ('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (str(HISTORICAL_EDGE_DB_SCHEMA_VERSION),),
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS historical_datasets (
            dataset_id TEXT PRIMARY KEY,
            market_type TEXT NOT NULL,
            source TEXT NOT NULL,
            first_observation_at TEXT NOT NULL,
            last_observation_at TEXT NOT NULL,
            observation_count INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS historical_outcomes (
            setup_id TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            split TEXT NOT NULL,
            market_type TEXT NOT NULL,
            strategy TEXT NOT NULL,
            symbol TEXT NOT NULL,
            regime TEXT NOT NULL,
            score_band TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            closed_at TEXT NOT NULL,
            outcome_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS historical_edge_reports (
            result_hash TEXT PRIMARY KEY,
            market_type TEXT NOT NULL,
            strategy TEXT NOT NULL,
            split TEXT NOT NULL,
            symbol TEXT,
            regime TEXT,
            score_band TEXT,
            evidence_quality TEXT NOT NULL,
            sample_count INTEGER NOT NULL,
            report_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_historical_outcomes_segment "
        "ON historical_outcomes(market_type, strategy, split)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_historical_edge_reports_segment "
        "ON historical_edge_reports(market_type, strategy, split)"
    )
