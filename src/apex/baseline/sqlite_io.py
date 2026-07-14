"""SQLite persistence for frozen V2 baseline reports."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from apex.baseline.contracts import BaselineEvaluationReport
from apex.baseline.evaluation import baseline_report_to_payload

BASELINE_REPORT_DB_SCHEMA_VERSION = 1


def write_baseline_report_sqlite(
    path: str | Path,
    report: BaselineEvaluationReport,
) -> None:
    """Upsert one complete baseline report by deterministic report id."""

    payload = baseline_report_to_payload(report)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    with sqlite3.connect(Path(path)) as connection:
        _ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO baseline_reports(report_id, plan_id, payload_json)
            VALUES (?, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
                plan_id = excluded.plan_id,
                payload_json = excluded.payload_json
            """,
            (report.report_id, report.plan_id, encoded),
        )
        connection.commit()


def load_baseline_report_sqlite(
    path: str | Path,
    report_id: str,
) -> dict[str, object]:
    """Load one baseline report payload by deterministic report id."""

    with sqlite3.connect(Path(path)) as connection:
        _ensure_schema(connection)
        row = connection.execute(
            "SELECT payload_json FROM baseline_reports WHERE report_id = ?",
            (report_id,),
        ).fetchone()
    if row is None:
        raise KeyError(report_id)
    payload = json.loads(str(row[0]))
    if not isinstance(payload, dict):
        raise ValueError("stored baseline report payload must be an object")
    return payload


def list_baseline_report_metadata_sqlite(path: str | Path) -> tuple[dict[str, str], ...]:
    """List lightweight baseline report identities in stable order."""

    with sqlite3.connect(Path(path)) as connection:
        _ensure_schema(connection)
        rows = connection.execute(
            "SELECT report_id, plan_id FROM baseline_reports ORDER BY report_id"
        ).fetchall()
    return tuple({"report_id": str(row[0]), "plan_id": str(row[1])} for row in rows)


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS baseline_reports (
            report_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    connection.execute("PRAGMA user_version = " + str(BASELINE_REPORT_DB_SCHEMA_VERSION))
