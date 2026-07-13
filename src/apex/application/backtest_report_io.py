"""Stable JSON serialization for chronological backtest reports."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

BACKTEST_REPORT_DB_SCHEMA_VERSION = 1
BACKTEST_CAMPAIGN_DB_SCHEMA_VERSION = 1


def make_run_id(*, symbol: str, replay_timeframe: str, dataset_hash: str, config_hash: str) -> str:
    """Create a stable, readable identity for a baseline run."""
    slug = symbol.lower().replace("/", "-").replace("_", "-")
    timeframe = replay_timeframe.lower().replace("/", "-")
    return f"{slug}-{timeframe}-{dataset_hash[:12]}-{config_hash[:12]}"


def to_json_value(value: Any) -> Any:
    """Convert supported domain values into explicit JSON-compatible values."""
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return to_json_value(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("report datetimes must be timezone-aware")
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): to_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported report value: {type(value).__name__}")


def dumps_report(payload: Any) -> str:
    """Serialize a report deterministically with explicit type conversion."""
    return json.dumps(to_json_value(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_backtest_report(path: Path, payload: Any, *, force: bool = False) -> None:
    """Atomically write a report while protecting existing files."""
    if path.exists() and not force:
        raise ValueError(f"refusing to overwrite existing report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(dumps_report(payload), encoding="utf-8")
    temporary.replace(path)


def load_backtest_report(path: Path) -> dict[str, Any]:
    """Load one saved JSON report."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid backtest report {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("backtest report must contain a JSON object")
    return payload


def write_backtest_report_sqlite(path: Path, payload: Mapping[str, Any]) -> None:
    """Index one chronological backtest report in local SQLite storage."""

    normalized = to_json_value(payload)
    if not isinstance(normalized, dict):
        raise ValueError("backtest report payload must be a mapping")
    run_id = _report_run_id(normalized)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_backtest_schema(connection)
        metadata = normalized.get("metadata", {})
        metrics = normalized.get("metrics", {})
        if not isinstance(metadata, dict) or not isinstance(metrics, dict):
            raise ValueError("backtest report requires metadata and metrics mappings")
        connection.execute(
            """
            INSERT INTO backtest_reports (
                run_id,
                schema_version,
                symbol,
                dataset_source,
                dataset_hash,
                config_hash,
                replay_timeframe,
                total_trades,
                net_profit,
                maximum_drawdown,
                report_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                schema_version=excluded.schema_version,
                symbol=excluded.symbol,
                dataset_source=excluded.dataset_source,
                dataset_hash=excluded.dataset_hash,
                config_hash=excluded.config_hash,
                replay_timeframe=excluded.replay_timeframe,
                total_trades=excluded.total_trades,
                net_profit=excluded.net_profit,
                maximum_drawdown=excluded.maximum_drawdown,
                report_json=excluded.report_json
            """,
            (
                run_id,
                BACKTEST_REPORT_DB_SCHEMA_VERSION,
                str(normalized.get("symbol", "")),
                str(normalized.get("dataset_source", "")),
                str(metadata.get("dataset_hash", "")),
                str(metadata.get("config_hash", "")),
                str(metadata.get("replay_timeframe", "")),
                int(metrics.get("total_trades", 0)),
                float(metrics.get("net_profit", 0.0)),
                float(metrics.get("maximum_drawdown", 0.0)),
                dumps_report(normalized),
            ),
        )


def load_backtest_report_sqlite(path: Path, run_id: str) -> dict[str, Any] | None:
    """Load one indexed backtest report by run identity."""

    if not path.exists():
        return None
    with sqlite3.connect(path) as connection:
        _ensure_backtest_schema(connection)
        row = connection.execute(
            "SELECT report_json FROM backtest_reports WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    loaded = json.loads(row[0])
    if not isinstance(loaded, dict):
        raise ValueError("stored backtest report must contain a JSON object")
    return loaded


def list_backtest_report_metadata_sqlite(
    path: Path, *, limit: int = 100
) -> tuple[dict[str, Any], ...]:
    """List indexed backtest report metadata without loading full reports."""

    if limit <= 0:
        raise ValueError("backtest report metadata limit must be positive")
    if not path.exists():
        return ()
    with sqlite3.connect(path) as connection:
        _ensure_backtest_schema(connection)
        rows = connection.execute(
            """
            SELECT
                run_id,
                schema_version,
                symbol,
                dataset_source,
                dataset_hash,
                config_hash,
                replay_timeframe,
                total_trades,
                net_profit,
                maximum_drawdown
            FROM backtest_reports
            ORDER BY run_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return tuple(
        {
            "run_id": row[0],
            "schema_version": row[1],
            "symbol": row[2],
            "dataset_source": row[3],
            "dataset_hash": row[4],
            "config_hash": row[5],
            "replay_timeframe": row[6],
            "total_trades": row[7],
            "net_profit": row[8],
            "maximum_drawdown": row[9],
        }
        for row in rows
    )


def write_backtest_campaign_sqlite(path: Path, payload: Mapping[str, Any]) -> None:
    """Index one chronological campaign report in local SQLite storage."""

    normalized = to_json_value(payload)
    if not isinstance(normalized, dict):
        raise ValueError("backtest campaign payload must be a mapping")
    campaign_id = _campaign_id_from_payload(normalized)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        _ensure_backtest_campaign_schema(connection)
        rankings = normalized.get("rankings", [])
        if not isinstance(rankings, list):
            raise ValueError("backtest campaign rankings must be a list")
        best = rankings[0] if rankings else {}
        if not isinstance(best, dict):
            best = {}
        connection.execute(
            """
            INSERT INTO backtest_campaigns (
                campaign_id,
                schema_version,
                symbol,
                dataset_source,
                variant_count,
                best_variant_id,
                best_net_profit,
                best_maximum_drawdown,
                campaign_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(campaign_id) DO UPDATE SET
                schema_version=excluded.schema_version,
                symbol=excluded.symbol,
                dataset_source=excluded.dataset_source,
                variant_count=excluded.variant_count,
                best_variant_id=excluded.best_variant_id,
                best_net_profit=excluded.best_net_profit,
                best_maximum_drawdown=excluded.best_maximum_drawdown,
                campaign_json=excluded.campaign_json
            """,
            (
                campaign_id,
                BACKTEST_CAMPAIGN_DB_SCHEMA_VERSION,
                str(normalized.get("symbol", "")),
                str(normalized.get("dataset_source", "")),
                int(normalized.get("variant_count", 0)),
                str(normalized.get("best_variant_id", "")),
                float(best.get("net_profit", 0.0)),
                float(best.get("maximum_drawdown", 0.0)),
                dumps_report(normalized),
            ),
        )


def load_backtest_campaign_sqlite(path: Path, campaign_id: str) -> dict[str, Any] | None:
    """Load one indexed campaign report by stable campaign identity."""

    if not path.exists():
        return None
    with sqlite3.connect(path) as connection:
        _ensure_backtest_campaign_schema(connection)
        row = connection.execute(
            "SELECT campaign_json FROM backtest_campaigns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
    if row is None:
        return None
    loaded = json.loads(row[0])
    if not isinstance(loaded, dict):
        raise ValueError("stored backtest campaign must contain a JSON object")
    return loaded


def list_backtest_campaign_metadata_sqlite(
    path: Path, *, limit: int = 100
) -> tuple[dict[str, Any], ...]:
    """List indexed campaign metadata without loading full campaign reports."""

    if limit <= 0:
        raise ValueError("backtest campaign metadata limit must be positive")
    if not path.exists():
        return ()
    with sqlite3.connect(path) as connection:
        _ensure_backtest_campaign_schema(connection)
        rows = connection.execute(
            """
            SELECT
                campaign_id,
                schema_version,
                symbol,
                dataset_source,
                variant_count,
                best_variant_id,
                best_net_profit,
                best_maximum_drawdown
            FROM backtest_campaigns
            ORDER BY campaign_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return tuple(
        {
            "campaign_id": row[0],
            "schema_version": row[1],
            "symbol": row[2],
            "dataset_source": row[3],
            "variant_count": row[4],
            "best_variant_id": row[5],
            "best_net_profit": row[6],
            "best_maximum_drawdown": row[7],
        }
        for row in rows
    )


def _report_run_id(payload: Mapping[str, Any]) -> str:
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("backtest report metadata is required")
    run_id = metadata.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("backtest report metadata.run_id is required")
    return run_id


def _campaign_id_from_payload(payload: Mapping[str, Any]) -> str:
    campaign_id = payload.get("campaign_id")
    if not isinstance(campaign_id, str) or not campaign_id.strip():
        raise ValueError("backtest campaign payload requires campaign_id")
    return campaign_id


def _ensure_backtest_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS backtest_report_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO backtest_report_metadata (key, value)
        VALUES ('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(BACKTEST_REPORT_DB_SCHEMA_VERSION),),
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS backtest_reports (
            run_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            dataset_source TEXT NOT NULL,
            dataset_hash TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            replay_timeframe TEXT NOT NULL,
            total_trades INTEGER NOT NULL,
            net_profit REAL NOT NULL,
            maximum_drawdown REAL NOT NULL,
            report_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_backtest_reports_symbol ON backtest_reports(symbol)"
    )


def _ensure_backtest_campaign_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS backtest_campaign_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO backtest_campaign_metadata (key, value)
        VALUES ('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(BACKTEST_CAMPAIGN_DB_SCHEMA_VERSION),),
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS backtest_campaigns (
            campaign_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            dataset_source TEXT NOT NULL,
            variant_count INTEGER NOT NULL,
            best_variant_id TEXT NOT NULL,
            best_net_profit REAL NOT NULL,
            best_maximum_drawdown REAL NOT NULL,
            campaign_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_backtest_campaigns_symbol ON backtest_campaigns(symbol)"
    )
