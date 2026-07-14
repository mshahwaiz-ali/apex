"""SQLite persistence for curated manifests and audited outcome imports."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from apex.application.backtest_report_io import dumps_report, to_json_value
from apex.application.historical_dataset_manifest import CuratedDatasetManifest
from apex.application.historical_outcome_conversion import HistoricalOutcomeConversionSummary

HISTORICAL_DATASET_DB_SCHEMA_VERSION = 2


def write_curated_dataset_manifest_sqlite(
    path: Path,
    manifest: CuratedDatasetManifest,
    *,
    validation_state: str,
) -> None:
    """Idempotently persist one deterministic curated dataset manifest."""

    payload = _mapping_payload(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO historical_dataset_manifests (
                dataset_id, market_type, content_hash, validation_state, manifest_json
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id) DO UPDATE SET
                market_type=excluded.market_type,
                content_hash=excluded.content_hash,
                validation_state=excluded.validation_state,
                manifest_json=excluded.manifest_json
            """,
            (
                manifest.dataset_id,
                manifest.market_type.value,
                manifest.content_hash,
                validation_state,
                dumps_report(payload),
            ),
        )


def load_curated_dataset_manifest_sqlite(path: Path, dataset_id: str) -> dict[str, Any] | None:
    """Load a persisted manifest payload by stable dataset identity."""

    if not path.exists():
        return None
    with sqlite3.connect(path) as connection:
        _ensure_schema(connection)
        row = connection.execute(
            "SELECT manifest_json FROM historical_dataset_manifests WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchone()
    return None if row is None else _load_mapping(row[0], "stored manifest")


def write_historical_outcome_import_sqlite(
    path: Path,
    summary: HistoricalOutcomeConversionSummary,
) -> int:
    """Atomically upsert accepted outcomes and their reproducible import audit."""

    payload = _mapping_payload(summary)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_schema(connection)
        for outcome in summary.outcomes:
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
                    dumps_report(_mapping_payload(outcome)),
                ),
            )
        connection.execute(
            """
            INSERT INTO historical_outcome_imports (
                result_hash, dataset_id, source_identity, accepted_count,
                rejected_count, duplicate_count, import_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(result_hash) DO UPDATE SET
                dataset_id=excluded.dataset_id,
                source_identity=excluded.source_identity,
                accepted_count=excluded.accepted_count,
                rejected_count=excluded.rejected_count,
                duplicate_count=excluded.duplicate_count,
                import_json=excluded.import_json
            """,
            (
                summary.result_hash,
                summary.dataset_id,
                summary.source_identity,
                summary.accepted_count,
                summary.rejected_count,
                summary.duplicate_count,
                dumps_report(payload),
            ),
        )
    return summary.accepted_count


def load_historical_outcome_import_sqlite(
    path: Path, result_hash: str
) -> dict[str, Any] | None:
    """Load an audited import by deterministic result hash."""

    if not path.exists():
        return None
    with sqlite3.connect(path) as connection:
        _ensure_schema(connection)
        row = connection.execute(
            "SELECT import_json FROM historical_outcome_imports WHERE result_hash = ?",
            (result_hash,),
        ).fetchone()
    return None if row is None else _load_mapping(row[0], "stored outcome import")


def _mapping_payload(value: object) -> dict[str, Any]:
    normalized = to_json_value(value)
    if not isinstance(normalized, dict):
        raise TypeError("historical persistence payload must serialize to a mapping")
    return normalized


def _load_mapping(raw: str, label: str) -> dict[str, Any]:
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ValueError(f"{label} must be a JSON object")
    return loaded


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
    existing = connection.execute(
        "SELECT value FROM historical_edge_metadata WHERE key = 'schema_version'"
    ).fetchone()
    current = int(existing[0]) if existing is not None else 0
    connection.execute(
        """
        INSERT INTO historical_edge_metadata (key, value)
        VALUES ('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (str(max(current, HISTORICAL_DATASET_DB_SCHEMA_VERSION)),),
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS historical_dataset_manifests (
            dataset_id TEXT PRIMARY KEY,
            market_type TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            validation_state TEXT NOT NULL,
            manifest_json TEXT NOT NULL
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
        CREATE TABLE IF NOT EXISTS historical_outcome_imports (
            result_hash TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            source_identity TEXT NOT NULL,
            accepted_count INTEGER NOT NULL,
            rejected_count INTEGER NOT NULL,
            duplicate_count INTEGER NOT NULL,
            import_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_historical_dataset_manifests_market "
        "ON historical_dataset_manifests(market_type, dataset_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_historical_outcome_imports_source "
        "ON historical_outcome_imports(dataset_id, source_identity)"
    )
