"""Tests for empirical calibration report schema compatibility."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from apex.optimization.empirical import (
    S10_EMPIRICAL_REPORT_SCHEMA_VERSION,
    S10_SUPPORTED_EMPIRICAL_REPORT_SCHEMA_VERSIONS,
    load_and_verify_empirical_calibration_report,
)


def _write_hashed_payload(path: Path, payload: dict[str, object]) -> None:
    report_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    document = dict(payload)
    document["report_sha256"] = report_hash
    path.write_text(json.dumps(document), encoding="utf-8")


def test_loader_accepts_current_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "current.json"
    _write_hashed_payload(
        path,
        {
            "schema_version": S10_EMPIRICAL_REPORT_SCHEMA_VERSION,
            "selection": {},
        },
    )

    report = load_and_verify_empirical_calibration_report(path)

    assert report.payload["schema_version"] == S10_EMPIRICAL_REPORT_SCHEMA_VERSION


def test_loader_preserves_version_one_backward_compatibility(tmp_path: Path) -> None:
    path = tmp_path / "version-one.json"
    _write_hashed_payload(
        path,
        {
            "schema_version": 1,
            "selection": {},
        },
    )

    report = load_and_verify_empirical_calibration_report(path)

    assert 1 in S10_SUPPORTED_EMPIRICAL_REPORT_SCHEMA_VERSIONS
    assert report.payload["schema_version"] == 1


@pytest.mark.parametrize("schema_version", [None, "2", True, 0, 3])
def test_loader_rejects_missing_malformed_or_unsupported_schema(
    tmp_path: Path,
    schema_version: object,
) -> None:
    path = tmp_path / "invalid-schema.json"
    payload: dict[str, object] = {"selection": {}}
    if schema_version is not None:
        payload["schema_version"] = schema_version
    _write_hashed_payload(path, payload)

    with pytest.raises(ValueError, match="schema version"):
        load_and_verify_empirical_calibration_report(path)
