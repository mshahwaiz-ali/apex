"""Schema-versioned analysis record persistence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from apex.application.methodology_identity import METHODOLOGY_PATH, METHODOLOGY_VERSION

ANALYSIS_RECORD_SCHEMA_VERSION = 1
ANALYSIS_RECORD_DB_SCHEMA_VERSION = 1


def build_analysis_record(
    payload: Mapping[str, Any],
    *,
    provider: str = "configured-provider",
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    """Wrap a serialized analysis or scan payload with reproducibility metadata."""

    timestamp = recorded_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("analysis record timestamp must be timezone-aware")
    normalized_payload = _json_roundtrip(payload)
    source_type = "scan" if "results" in normalized_payload else "analysis"
    subject = _subject(normalized_payload)
    configuration_id = str(normalized_payload.get("configuration_id", "unknown"))
    scanner_type = normalized_payload.get("scanner_type")
    content_hash = _stable_hash(normalized_payload)
    identity = _stable_hash(
        {
            "source_type": source_type,
            "subject": subject,
            "generated_at": normalized_payload.get("generated_at"),
            "configuration_id": configuration_id,
            "scanner_type": scanner_type,
            "content_hash": content_hash,
        }
    )
    return {
        "schema_version": ANALYSIS_RECORD_SCHEMA_VERSION,
        "analysis_id": identity,
        "recorded_at": timestamp.isoformat(),
        "source_type": source_type,
        "provider": provider,
        "subject": subject,
        "configuration_id": configuration_id,
        "methodology_version": str(
            normalized_payload.get("methodology_version", METHODOLOGY_VERSION)
        ),
        "methodology_path": str(normalized_payload.get("methodology_path", METHODOLOGY_PATH)),
        "scanner_type": scanner_type,
        "content_hash": content_hash,
        "payload": normalized_payload,
    }


def write_analysis_record(path: Path, record: Mapping[str, Any], *, append: bool = True) -> None:
    """Write one analysis record as deterministic JSON or append-only JSONL."""

    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(_json_roundtrip(record), sort_keys=True, ensure_ascii=False) + "\n"
    if append:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
        return
    path.write_text(
        json.dumps(_json_roundtrip(record), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_analysis_record_sqlite(path: Path, record: Mapping[str, Any]) -> None:
    """Store one analysis record in a deterministic local SQLite database."""

    normalized = _json_roundtrip(record)
    _validate_record(normalized)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection, connection:
        _ensure_sqlite_schema(connection)
        connection.execute(
            """
            INSERT INTO analysis_records (
                analysis_id,
                schema_version,
                source_type,
                provider,
                subject,
                configuration_id,
                scanner_type,
                content_hash,
                recorded_at,
                payload_json,
                record_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(analysis_id) DO UPDATE SET
                schema_version=excluded.schema_version,
                source_type=excluded.source_type,
                provider=excluded.provider,
                subject=excluded.subject,
                configuration_id=excluded.configuration_id,
                scanner_type=excluded.scanner_type,
                content_hash=excluded.content_hash,
                recorded_at=excluded.recorded_at,
                payload_json=excluded.payload_json,
                record_json=excluded.record_json
            """,
            (
                normalized["analysis_id"],
                normalized["schema_version"],
                normalized["source_type"],
                normalized["provider"],
                normalized["subject"],
                normalized["configuration_id"],
                normalized.get("scanner_type"),
                normalized["content_hash"],
                normalized["recorded_at"],
                json.dumps(normalized["payload"], sort_keys=True, ensure_ascii=False),
                json.dumps(normalized, sort_keys=True, ensure_ascii=False),
            ),
        )


def load_analysis_record_sqlite(path: Path, analysis_id: str) -> dict[str, Any] | None:
    """Load one stored analysis record by stable identity."""

    if not path.exists():
        return None
    with closing(sqlite3.connect(path)) as connection, connection:
        _ensure_sqlite_schema(connection)
        row = connection.execute(
            "SELECT record_json FROM analysis_records WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchone()
    if row is None:
        return None
    return cast(dict[str, Any], json.loads(row[0]))


def list_analysis_record_metadata_sqlite(
    path: Path, *, limit: int = 100
) -> tuple[dict[str, Any], ...]:
    """List recent record metadata without loading full payload blobs."""

    if limit <= 0:
        raise ValueError("analysis record metadata limit must be positive")
    if not path.exists():
        return ()
    with closing(sqlite3.connect(path)) as connection, connection:
        _ensure_sqlite_schema(connection)
        rows = connection.execute(
            """
            SELECT
                analysis_id,
                schema_version,
                source_type,
                provider,
                subject,
                configuration_id,
                scanner_type,
                content_hash,
                recorded_at
            FROM analysis_records
            ORDER BY recorded_at DESC, analysis_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return tuple(
        {
            "analysis_id": row[0],
            "schema_version": row[1],
            "source_type": row[2],
            "provider": row[3],
            "subject": row[4],
            "configuration_id": row[5],
            "scanner_type": row[6],
            "content_hash": row[7],
            "recorded_at": row[8],
        }
        for row in rows
    )


def _subject(payload: Mapping[str, Any]) -> str:
    symbol = payload.get("symbol")
    if isinstance(symbol, str) and symbol:
        return symbol
    if "results" in payload:
        return "scan"
    return "unknown"


def _stable_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json_roundtrip(payload: Mapping[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(payload, sort_keys=True, default=str)))


def _ensure_sqlite_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_record_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO analysis_record_metadata (key, value)
        VALUES ('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(ANALYSIS_RECORD_DB_SCHEMA_VERSION),),
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_records (
            analysis_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            provider TEXT NOT NULL,
            subject TEXT NOT NULL,
            configuration_id TEXT NOT NULL,
            scanner_type TEXT,
            content_hash TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            record_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_records_subject ON analysis_records(subject)"
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_records_recorded_at
        ON analysis_records(recorded_at)
        """
    )


def _validate_record(record: Mapping[str, Any]) -> None:
    required = (
        "analysis_id",
        "schema_version",
        "source_type",
        "provider",
        "subject",
        "configuration_id",
        "content_hash",
        "recorded_at",
        "payload",
    )
    missing = [field for field in required if field not in record]
    if missing:
        raise ValueError(f"analysis record missing required fields: {', '.join(missing)}")
    if not isinstance(record["payload"], dict):
        raise ValueError("analysis record payload must be a mapping")
