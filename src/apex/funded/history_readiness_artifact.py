"""Seal history-backed funded-readiness reports with exact provenance."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

FUNDED_HISTORY_READINESS_ARTIFACT_SCHEMA_VERSION = 1

__all__ = [
    "FUNDED_HISTORY_READINESS_ARTIFACT_SCHEMA_VERSION",
    "build_funded_history_readiness_artifact",
    "load_and_verify_funded_history_readiness_artifact",
    "write_funded_history_readiness_artifact",
]


def build_funded_history_readiness_artifact(
    *,
    input_path: Path,
    history_review_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    """Build a deterministic artifact binding a funded-readiness review to aggregate validation history."""

    input_payload = _load_object(input_path, "funded-readiness input")
    history_payload = _load_object(history_review_path, "aggregate history review")
    report_payload = _load_object(report_path, "funded-readiness report")

    provider_name = _required_string(report_payload, "provider_name")
    if _input_provider_name(input_payload) != provider_name:
        raise ValueError("funded-readiness provider identity mismatch")

    ready = _required_bool(report_payload, "ready")
    history_ready = _required_bool(history_payload, "ready_for_funded_review")
    if ready and not history_ready:
        raise ValueError("ready funded report cannot use non-ready aggregate history")

    payload: dict[str, Any] = {
        "schema_version": FUNDED_HISTORY_READINESS_ARTIFACT_SCHEMA_VERSION,
        "provider_name": provider_name,
        "ready": ready,
        "history_ready_for_funded_review": history_ready,
        "sources": {
            "input": _source_descriptor(input_path),
            "history_review": _source_descriptor(history_review_path),
            "report": _source_descriptor(report_path),
        },
        "execution_authorized": False,
        "warnings": [
            "This artifact preserves aggregate-history-backed funded-readiness evidence only.",
            "It does not authorize funded, production, or real-money execution.",
        ],
    }
    payload["artifact_sha256"] = _hash_payload(payload)
    return payload


def write_funded_history_readiness_artifact(
    path: Path,
    payload: Mapping[str, Any],
    *,
    force: bool = False,
) -> None:
    """Persist one history-backed funded-readiness artifact atomically."""

    normalized = _verify_artifact(payload)
    if path.exists() and not force:
        raise FileExistsError(
            f"refusing to overwrite funded history-readiness artifact: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    if load_and_verify_funded_history_readiness_artifact(path) != normalized:
        path.unlink(missing_ok=True)
        raise ValueError("funded history-readiness artifact changed after reload")


def load_and_verify_funded_history_readiness_artifact(path: Path) -> dict[str, Any]:
    """Load and verify one sealed history-backed funded-readiness artifact."""

    return _verify_artifact(_load_object(path, "funded history-readiness artifact"))


def _verify_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _json_object(payload, "funded history-readiness artifact")
    if (
        normalized.get("schema_version")
        != FUNDED_HISTORY_READINESS_ARTIFACT_SCHEMA_VERSION
    ):
        raise ValueError("unsupported funded history-readiness artifact schema version")
    _required_string(normalized, "provider_name")
    ready = _required_bool(normalized, "ready")
    history_ready = _required_bool(normalized, "history_ready_for_funded_review")
    if ready and not history_ready:
        raise ValueError("ready funded report cannot use non-ready aggregate history")

    sources = normalized.get("sources")
    if not isinstance(sources, dict) or not all(
        isinstance(key, str) for key in sources
    ):
        raise TypeError("funded history-readiness artifact sources must be a JSON object")
    required_sources = {"input", "history_review", "report"}
    if set(sources) != required_sources:
        raise ValueError("funded history-readiness artifact source set is invalid")
    for label in sorted(required_sources):
        source = sources[label]
        if not isinstance(source, dict) or not all(
            isinstance(key, str) for key in source
        ):
            raise TypeError(
                f"funded history-readiness artifact {label} source must be an object"
            )
        _required_string(source, "name")
        _required_sha256(source, "sha256")

    if normalized.get("execution_authorized") is not False:
        raise ValueError("funded history-readiness artifact cannot authorize execution")
    artifact_hash = normalized.pop("artifact_sha256", None)
    if not isinstance(artifact_hash, str) or len(artifact_hash) != 64:
        raise ValueError("funded history-readiness artifact hash is missing")
    if _hash_payload(normalized) != artifact_hash:
        raise ValueError(
            "funded history-readiness artifact hash does not match its payload"
        )
    normalized["artifact_sha256"] = artifact_hash
    return normalized


def _input_provider_name(payload: Mapping[str, Any]) -> str:
    provider_limits = payload.get("provider_limits")
    if not isinstance(provider_limits, Mapping):
        raise TypeError("funded-readiness input provider_limits must be an object")
    return _required_string(provider_limits, "provider_name")


def _source_descriptor(path: Path) -> dict[str, str]:
    return {
        "name": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _load_object(path: Path, label: str) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _json_object(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    loaded: object = json.loads(json.dumps(value))
    if not isinstance(loaded, dict) or not all(isinstance(key, str) for key in loaded):
        raise TypeError(f"{label} must be a JSON object")
    return cast(dict[str, Any], loaded)


def _required_string(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"funded history-readiness artifact {field_name} is missing")
    return value.strip()


def _required_bool(payload: Mapping[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise TypeError(
            f"funded history-readiness artifact {field_name} must be boolean"
        )
    return value


def _required_sha256(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_string(payload, field_name)
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(
            f"funded history-readiness artifact {field_name} must be lowercase SHA-256"
        )
    return value


def _hash_payload(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
