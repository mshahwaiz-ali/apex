"""Tests for atomic shared historical futures artifact persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apex.backtesting.historical_futures_shared_io import hash_json, write_shared_artifacts


def _payloads() -> tuple[dict[str, object], dict[str, object], str]:
    result: dict[str, object] = {
        "campaign_id": "campaign-1",
        "trades": [],
        "shared_wallet": {},
    }
    result_hash = hash_json(result)
    manifest: dict[str, object] = {
        "campaign_id": "campaign-1",
        "result_hash": result_hash,
        "trade_count": 0,
    }
    return result, manifest, result_hash


def test_shared_artifacts_round_trip(tmp_path: Path) -> None:
    result, manifest, result_hash = _payloads()
    result_path = tmp_path / "result.json"
    manifest_path = tmp_path / "manifest.json"

    write_shared_artifacts(
        result_path=result_path,
        manifest_path=manifest_path,
        result_payload=result,
        manifest_payload=manifest,
        expected_result_hash=result_hash,
    )

    assert json.loads(result_path.read_text(encoding="utf-8")) == result
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    assert not result_path.with_suffix(".json.tmp").exists()
    assert not manifest_path.with_suffix(".json.tmp").exists()


def test_shared_artifacts_refuse_overwrite(tmp_path: Path) -> None:
    result, manifest, result_hash = _payloads()
    result_path = tmp_path / "result.json"
    manifest_path = tmp_path / "manifest.json"
    result_path.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refuses to overwrite"):
        write_shared_artifacts(
            result_path=result_path,
            manifest_path=manifest_path,
            result_payload=result,
            manifest_payload=manifest,
            expected_result_hash=result_hash,
        )

    assert result_path.read_text(encoding="utf-8") == "existing"
    assert not manifest_path.exists()


def test_shared_artifacts_reject_duplicate_paths(tmp_path: Path) -> None:
    result, manifest, result_hash = _payloads()
    duplicate = tmp_path / "artifact.json"

    with pytest.raises(ValueError, match="paths must be unique"):
        write_shared_artifacts(
            result_path=duplicate,
            manifest_path=duplicate,
            result_payload=result,
            manifest_payload=manifest,
            expected_result_hash=result_hash,
        )


def test_shared_artifacts_cleanup_result_when_manifest_hash_is_wrong(tmp_path: Path) -> None:
    result, manifest, result_hash = _payloads()
    manifest["result_hash"] = "0" * 64
    result_path = tmp_path / "result.json"
    manifest_path = tmp_path / "manifest.json"

    with pytest.raises(ValueError, match="manifest result hash mismatch"):
        write_shared_artifacts(
            result_path=result_path,
            manifest_path=manifest_path,
            result_payload=result,
            manifest_payload=manifest,
            expected_result_hash=result_hash,
        )

    assert not result_path.exists()
    assert not manifest_path.exists()
    assert not result_path.with_suffix(".json.tmp").exists()
    assert not manifest_path.with_suffix(".json.tmp").exists()
