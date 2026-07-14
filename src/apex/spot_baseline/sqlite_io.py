"""SQLite persistence for frozen spot baseline reports."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from apex.spot_baseline.contracts import SpotBaselineReport
from apex.spot_baseline.evaluation import spot_baseline_report_to_payload

SPOT_BASELINE_REPORT_DB_SCHEMA_VERSION = 1


def write_spot_baseline_report_sqlite(
    path: str | Path,
    report: SpotBaselineReport,
) -> None:
    """Upsert one report by deterministic report id."""
    encoded = json.dumps(
        spot_baseline_report_to_payload(report),
        sort_keys=True,
        separators=(",", ":"),
    )
    with sqlite3.connect(Path(path)) as connection:
        _ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO spot_baseline_reports(report_id, plan_id, payload_json)
            VALUES (?, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
                plan_id = excluded.plan_id,
                payload_json = excluded.payload_json
            """,
            (report.report_id, report.plan_id, encoded),
        )
        connection.commit()


def load_spot_baseline_report_sqlite(
    path: str | Path,
    report_id: str,
) -> dict[str, object]:
    """Load one report payload by id."""
    with sqlite3.connect(Path(path)) as connection:
        _ensure_schema(connection)
        row = connection.execute(
            "SELECT payload_json FROM spot_baseline_reports WHERE report_id = ?",
            (report_id,),
        ).fetchone()
    if row is None:
        raise KeyError(report_id)
    payload = json.loads(str(row[0]))
    if not isinstance(payload, dict):
        raise ValueError("stored spot baseline report payload must be an object")
    return payload


def list_spot_baseline_report_metadata_sqlite(
    path: str | Path,
) -> tuple[dict[str, str], ...]:
    """List report identities in deterministic order."""
    with sqlite3.connect(Path(path)) as connection:
        _ensure_schema(connection)
        rows = connection.execute(
            "SELECT report_id, plan_id FROM spot_baseline_reports ORDER BY report_id"
        ).fetchall()
    return tuple(
        {"report_id": str(row[0]), "plan_id": str(row[1])} for row in rows
    )


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS spot_baseline_reports (
            report_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "PRAGMA user_version = " + str(SPOT_BASELINE_REPORT_DB_SCHEMA_VERSION)
    )
