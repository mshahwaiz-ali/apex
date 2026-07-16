"""Seal forward-edge reports with reproducible source provenance and self-hashing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, cast

FORWARD_EDGE_ARTIFACT_SCHEMA_VERSION = 1

__all__ = [
    "FORWARD_EDGE_ARTIFACT_SCHEMA_VERSION",
    "build_forward_edge_artifact",
    "load_and_verify_forward_edge_artifact",
    "write_forward_edge_artifact",
]


def build_forward_edge_artifact(
    report: Mapping[str, Any],
    *,
    historical_validation_path: Path,
) -> dict[str, Any]:
    """Build a deterministic sealed forward-edge artifact."""

    source_bytes = historical_validation_path.read_bytes()
    report_payload = _json_object(report, "forward edge report")
    payload: dict[str, Any] = {
        "schema_version": FORWARD_EDGE_ARTIFACT_SCHEMA_VERSION,
        "source": {
            "historical_validation_name": historical_validation_path.name,
            "historical_validation_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "source_validation_report_id": _required_string(
                report_payload,
                "source_validation_report_id",
            ),
            "campaign_id": _required_string(report_payload, "campaign_id"),
        },
        "forward_edge_report": report_payload,
        "execution_authorized": False,
        "warnings": [
            "This artifact records historical and forward-paper evidence only.",
            "It does not authorize testnet or real-money execution.",
        ],
    }
    payload["artifact_sha256"] = _hash_payload(payload)
    return payload


def write_forward_edge_artifact(
    path: Path,
    payload: Mapping[str, Any],
    *,
    force: bool = False,
) -> None:
    """Persist a sealed artifact atomically without silent overwrite."""

    normalized = _verify_artifact(payload)
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite forward edge artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    if load_and_verify_forward_edge_artifact(path) != normalized:
        path.unlink(missing_ok=True)
        raise ValueError("forward edge artifact changed after reload")


def load_and_verify_forward_edge_artifact(path: Path) -> dict[str, Any]:
    """Load and verify one sealed forward-edge artifact."""

    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("forward edge artifact must be a JSON object")
    return _verify_artifact(cast(dict[str, Any], value))


def _verify_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _json_object(payload, "forward edge artifact")
    if normalized.get("schema_version") != FORWARD_EDGE_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported forward edge artifact schema version")
    source = normalized.get("source")
    if not isinstance(source, dict) or not all(isinstance(key, str) for key in source):
        raise TypeError("forward edge artifact source must be a JSON object")
    _required_string(source, "historical_validation_name")
    _required_sha256(source, "historical_validation_sha256")
    _required_string(source, "source_validation_report_id")
    _required_string(source, "campaign_id")
    report = normalized.get("forward_edge_report")
    if not isinstance(report, dict) or not all(isinstance(key, str) for key in report):
        raise TypeError("forward edge artifact report must be a JSON object")
    if report.get("source_validation_report_id") != source["source_validation_report_id"]:
        raise ValueError("forward edge artifact source report identity mismatch")
    if report.get("campaign_id") != source["campaign_id"]:
        raise ValueError("forward edge artifact campaign identity mismatch")
    if normalized.get("execution_authorized") is not False:
        raise ValueError("forward edge artifact cannot authorize execution")
    artifact_hash = normalized.pop("artifact_sha256", None)
    if not isinstance(artifact_hash, str) or len(artifact_hash) != 64:
        raise ValueError("forward edge artifact hash is missing")
    if _hash_payload(normalized) != artifact_hash:
        raise ValueError("forward edge artifact hash does not match its payload")
    normalized["artifact_sha256"] = artifact_hash
    return normalized


def _json_object(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    loaded: object = json.loads(json.dumps(value))
    if not isinstance(loaded, dict) or not all(isinstance(key, str) for key in loaded):
        raise TypeError(f"{label} must be a JSON object")
    return cast(dict[str, Any], loaded)


def _required_string(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"forward edge artifact {field_name} is missing")
    return value.strip()


def _required_sha256(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_string(payload, field_name)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"forward edge artifact {field_name} must be lowercase SHA-256")
    return value


def _hash_payload(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
