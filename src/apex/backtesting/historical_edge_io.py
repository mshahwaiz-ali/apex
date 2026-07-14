"""Stable JSON and SQLite persistence for historical edge profiles."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from apex.application.backtest_report_io import dumps_report, to_json_value
from apex.backtesting.historical_edge import HistoricalEdgeProfile

HISTORICAL_EDGE_REPORT_SCHEMA_VERSION = 1
HISTORICAL_EDGE_DB_SCHEMA_VERSION = 1


def build_historical_edge_report(
    profiles: Sequence[HistoricalEdgeProfile],
    *,
    generated_at: datetime,
    source_type: str,
    source_id: str,
) -> dict[str, Any]:
    """Build one deterministic schema-versioned historical edge report."""

    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("historical edge report time must be timezone-aware")
    if not source_type.strip() or not source_id.strip():
        raise ValueError("historical edge report source type and source id are required")

    normalized_profiles = [to_json_value(profile) for profile in profiles]
    report_id = _historical_edge_report_id(
        source_type=source_type,
        source_id=source_id,
        profiles=normalized_profiles,
    )
    return {
        "schema_version": HISTORICAL_EDGE_REPORT_SCHEMA_VERSION,
        "report_id": report_id,
        "generated_at": generated_at.isoformat(),
        "source_type": source_type,
        "source_id": source_id,
        "profile_count": len(normalized_profiles),
        "profiles": normalized_profiles,
    }


def write_historical_edge_report(
    path: Path,
    payload: Mapping[str, Any],
    *,
    force: bool = False,
) -> None:
    """Atomically write a historical edge report as deterministic JSON."""

    normalized = _normalize_report(payload)
    if path.exists() and not force:
        raise ValueError(f"refusing to overwrite existing report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(dumps_report(normalized), encoding="utf-8")
    temporary.replace(path)


def load_historical_edge_report(path: Path) -> dict[str, Any]:
    """Load and validate one historical edge JSON report."""

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical edge report {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError("historical edge report must contain a JSON object")
    return _normalize_report(loaded)


def write_historical_edge_report_sqlite(
    path: Path,
    payload: Mapping[str, Any],
) -> None:
    """Upsert one historical edge report into local SQLite storage."""

    normalized = _normalize_report(payload)
    report_id = str(normalized["report_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection, connection:
        _ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO historical_edge_reports (
                report_id,
                schema_version,
                generated_at,
                source_type,
                source_id,
                profile_count,
                report_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
                schema_version=excluded.schema_version,
                generated_at=excluded.generated_at,
                source_type=excluded.source_type,
                source_id=excluded.source_id,
                profile_count=excluded.profile_count,
                report_json=excluded.report_json
            """,
            (
                report_id,
                HISTORICAL_EDGE_DB_SCHEMA_VERSION,
                str(normalized["generated_at"]),
                str(normalized["source_type"]),
                str(normalized["source_id"]),
                int(normalized["profile_count"]),
                dumps_report(normalized),
            ),
        )


def load_historical_edge_report_sqlite(
    path: Path,
    report_id: str,
) -> dict[str, Any] | None:
    """Load one historical edge report from SQLite by report identity."""

    if not report_id.strip():
        raise ValueError("historical edge report id cannot be empty")
    if not path.exists():
        return None
    with closing(sqlite3.connect(path)) as connection, connection:
        _ensure_schema(connection)
        row = connection.execute(
            "SELECT report_json FROM historical_edge_reports WHERE report_id = ?",
            (report_id,),
        ).fetchone()
    if row is None:
        return None
    loaded = json.loads(row[0])
    if not isinstance(loaded, dict):
        raise ValueError("stored historical edge report must contain a JSON object")
    return _normalize_report(loaded)


def list_historical_edge_report_metadata_sqlite(
    path: Path,
    *,
    limit: int = 100,
) -> tuple[dict[str, Any], ...]:
    """List indexed historical edge report metadata without full payloads."""

    if limit <= 0:
        raise ValueError("historical edge report metadata limit must be positive")
    if not path.exists():
        return ()
    with closing(sqlite3.connect(path)) as connection, connection:
        _ensure_schema(connection)
        rows = connection.execute(
            """
            SELECT
                report_id,
                schema_version,
                generated_at,
                source_type,
                source_id,
                profile_count
            FROM historical_edge_reports
            ORDER BY report_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return tuple(
        {
            "report_id": row[0],
            "schema_version": row[1],
            "generated_at": row[2],
            "source_type": row[3],
            "source_id": row[4],
            "profile_count": row[5],
        }
        for row in rows
    )


def _historical_edge_report_id(
    *,
    source_type: str,
    source_id: str,
    profiles: Sequence[Any],
) -> str:
    identity = dumps_report(
        {
            "source_type": source_type,
            "source_id": source_id,
            "profiles": profiles,
        }
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"historical-edge-{digest[:24]}"


def _normalize_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = to_json_value(payload)
    if not isinstance(normalized, dict):
        raise ValueError("historical edge report payload must be a mapping")
    required = {
        "schema_version",
        "report_id",
        "generated_at",
        "source_type",
        "source_id",
        "profile_count",
        "profiles",
    }
    missing = required.difference(normalized)
    if missing:
        raise ValueError(f"historical edge report fields are missing: {sorted(missing)}")
    if normalized["schema_version"] != HISTORICAL_EDGE_REPORT_SCHEMA_VERSION:
        raise ValueError("unsupported historical edge report schema version")
    for field_name in ("report_id", "generated_at", "source_type", "source_id"):
        value = normalized[field_name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"historical edge report {field_name} is required")
    profiles = normalized["profiles"]
    if not isinstance(profiles, list):
        raise ValueError("historical edge report profiles must be a list")
    if normalized["profile_count"] != len(profiles):
        raise ValueError("historical edge report profile count must match profiles")
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
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(HISTORICAL_EDGE_DB_SCHEMA_VERSION),),
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS historical_edge_reports (
            report_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            generated_at TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            profile_count INTEGER NOT NULL,
            report_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_historical_edge_source
        ON historical_edge_reports(source_type, source_id)
        """
    )
