"""Tests for schema-versioned analysis record persistence."""

import json
from datetime import UTC, datetime
from pathlib import Path

from apex.application import (
    build_analysis_record,
    list_analysis_record_metadata_sqlite,
    load_analysis_record_sqlite,
    write_analysis_record,
    write_analysis_record_sqlite,
)
from apex.application.analysis import write_json_report

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)


def _payload() -> dict[str, object]:
    return {
        "symbol": "BTC/USDT",
        "generated_at": NOW.isoformat(),
        "configuration_id": "cfg-test",
        "scanner_type": "NORMAL_MARKET",
        "decision": "NO_TRADE",
    }


def test_analysis_record_identity_is_stable() -> None:
    first = build_analysis_record(_payload(), recorded_at=NOW)
    second = build_analysis_record(_payload(), recorded_at=NOW)

    assert first["schema_version"] == 1
    assert first["analysis_id"] == second["analysis_id"]
    assert first["content_hash"] == second["content_hash"]
    assert first["subject"] == "BTC/USDT"


def test_analysis_record_identity_changes_with_payload() -> None:
    first = build_analysis_record(_payload(), recorded_at=NOW)
    changed = _payload()
    changed["decision"] = "LONG"
    second = build_analysis_record(changed, recorded_at=NOW)

    assert first["analysis_id"] != second["analysis_id"]


def test_write_analysis_record_appends_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "analysis.jsonl"
    record = build_analysis_record(_payload(), recorded_at=NOW)

    write_analysis_record(path, record)
    write_analysis_record(path, record)

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["analysis_id"] for row in rows] == [record["analysis_id"], record["analysis_id"]]


def test_write_analysis_record_sqlite_upserts_and_loads_record(
    tmp_path: Path,
) -> None:
    path = tmp_path / "analysis.db"
    record = build_analysis_record(_payload(), recorded_at=NOW)

    write_analysis_record_sqlite(path, record)
    write_analysis_record_sqlite(path, record)

    loaded = load_analysis_record_sqlite(path, str(record["analysis_id"]))
    assert loaded == record
    metadata = list_analysis_record_metadata_sqlite(path)
    assert len(metadata) == 1
    assert metadata[0]["analysis_id"] == record["analysis_id"]
    assert metadata[0]["subject"] == "BTC/USDT"
    assert metadata[0]["content_hash"] == record["content_hash"]


def test_sqlite_record_helpers_handle_missing_database(tmp_path: Path) -> None:
    path = tmp_path / "missing.db"

    assert load_analysis_record_sqlite(path, "missing") is None
    assert list_analysis_record_metadata_sqlite(path) == ()


def test_write_json_report_embeds_record_metadata(tmp_path: Path) -> None:
    path = tmp_path / "report.json"

    write_json_report(_payload(), path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["record_metadata"]["analysis_id"]
    assert "payload" not in payload["record_metadata"]
