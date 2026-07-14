"""JSON and SQLite persistence for walk-forward calibration reports."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from apex.calibration.contracts import WalkForwardCalibrationReport
from apex.calibration.selection import calibration_report_to_payload

CALIBRATION_REPORT_SCHEMA_VERSION = 1
CALIBRATION_REPORT_DB_SCHEMA_VERSION = 1


def write_calibration_report(
    path: str | Path,
    report: WalkForwardCalibrationReport,
    *,
    force: bool = False,
) -> Path:
    target = Path(path)
    if target.exists() and not force:
        raise ValueError(f"calibration report already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(calibration_report_to_payload(report), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def load_calibration_report_payload(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("calibration report must contain a JSON object")
    if payload.get("schema_version") != CALIBRATION_REPORT_SCHEMA_VERSION:
        raise ValueError("unsupported calibration report schema version")
    if not isinstance(payload.get("report_id"), str) or not payload["report_id"]:
        raise ValueError("calibration report id is required")
    return payload


def write_calibration_report_sqlite(
    path: str | Path,
    report: WalkForwardCalibrationReport,
) -> None:
    payload = calibration_report_to_payload(report)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    with sqlite3.connect(Path(path)) as connection:
        _ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO calibration_reports(report_id, payload_json)
            VALUES (?, ?)
            ON CONFLICT(report_id) DO UPDATE SET payload_json = excluded.payload_json
            """,
            (report.report_id, encoded),
        )
        connection.commit()


def load_calibration_report_sqlite(
    path: str | Path,
    report_id: str,
) -> dict[str, object]:
    with sqlite3.connect(Path(path)) as connection:
        _ensure_schema(connection)
        row = connection.execute(
            "SELECT payload_json FROM calibration_reports WHERE report_id = ?",
            (report_id,),
        ).fetchone()
    if row is None:
        raise KeyError(report_id)
    payload = json.loads(str(row[0]))
    if not isinstance(payload, dict):
        raise ValueError("stored calibration report payload must be an object")
    return payload


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_reports (
            report_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
        """
    )
    connection.execute("PRAGMA user_version = " + str(CALIBRATION_REPORT_DB_SCHEMA_VERSION))
