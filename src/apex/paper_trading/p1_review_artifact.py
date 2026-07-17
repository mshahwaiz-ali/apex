"""Seal forward-validation review reports with reproducible source provenance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, cast

from apex.paper_trading.forward_review import load_and_verify_forward_paper_review_report

P1_REVIEW_ARTIFACT_SCHEMA_VERSION = 1

__all__ = [
    "P1_REVIEW_ARTIFACT_SCHEMA_VERSION",
    "build_p1_review_artifact",
    "load_and_verify_p1_review_artifact",
    "write_p1_review_artifact",
]


def build_p1_review_artifact(
    *,
    review_report_path: Path,
    historical_profile_path: Path,
    forward_profile_path: Path,
    daily_report_path: Path,
    paper_store_path: Path,
) -> dict[str, Any]:
    """Build a deterministic artifact binding one forward-validation review to all source files."""

    review = load_and_verify_forward_paper_review_report(review_report_path)
    source_paths = {
        "review_report": review_report_path,
        "historical_profile": historical_profile_path,
        "forward_profile": forward_profile_path,
        "daily_report": daily_report_path,
        "paper_store": paper_store_path,
    }
    sources = {
        label: {
            "name": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for label, path in source_paths.items()
    }
    payload: dict[str, Any] = {
        "schema_version": P1_REVIEW_ARTIFACT_SCHEMA_VERSION,
        "review_report_sha256": review.report_sha256,
        "review_state": str(review.payload["review_state"]),
        "sources": sources,
        "execution_authorized": False,
        "warnings": [
            "This artifact preserves forward-validation review evidence only.",
            "It does not authorize testnet, funded, or real-money execution.",
        ],
    }
    payload["artifact_sha256"] = _hash_payload(payload)
    return payload


def write_p1_review_artifact(
    path: Path,
    payload: Mapping[str, Any],
    *,
    force: bool = False,
) -> None:
    """Persist one sealed forward-validation review artifact atomically and reload-verify it."""

    normalized = _verify_artifact(payload)
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite P1 review artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    if load_and_verify_p1_review_artifact(path) != normalized:
        path.unlink(missing_ok=True)
        raise ValueError("P1 review artifact changed after reload")


def load_and_verify_p1_review_artifact(path: Path) -> dict[str, Any]:
    """Load and verify one sealed forward-validation review artifact."""

    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("P1 review artifact must be a JSON object")
    return _verify_artifact(cast(dict[str, Any], value))


def _verify_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _json_object(payload)
    if normalized.get("schema_version") != P1_REVIEW_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported P1 review artifact schema version")
    _required_sha256(normalized, "review_report_sha256")
    _required_string(normalized, "review_state")
    sources = normalized.get("sources")
    if not isinstance(sources, dict) or not all(isinstance(key, str) for key in sources):
        raise TypeError("P1 review artifact sources must be a JSON object")
    required_sources = {
        "review_report",
        "historical_profile",
        "forward_profile",
        "daily_report",
        "paper_store",
    }
    if set(sources) != required_sources:
        raise ValueError("P1 review artifact source set is invalid")
    for label in sorted(required_sources):
        source = sources[label]
        if not isinstance(source, dict) or not all(isinstance(key, str) for key in source):
            raise TypeError(f"P1 review artifact {label} source must be a JSON object")
        _required_string(source, "name")
        _required_sha256(source, "sha256")
    if normalized.get("execution_authorized") is not False:
        raise ValueError("P1 review artifact cannot authorize execution")
    artifact_hash = normalized.pop("artifact_sha256", None)
    if not isinstance(artifact_hash, str) or len(artifact_hash) != 64:
        raise ValueError("P1 review artifact hash is missing")
    if _hash_payload(normalized) != artifact_hash:
        raise ValueError("P1 review artifact hash does not match its payload")
    normalized["artifact_sha256"] = artifact_hash
    return normalized


def _json_object(value: Mapping[str, Any]) -> dict[str, Any]:
    loaded: object = json.loads(json.dumps(value))
    if not isinstance(loaded, dict) or not all(isinstance(key, str) for key in loaded):
        raise TypeError("P1 review artifact must be a JSON object")
    return cast(dict[str, Any], loaded)


def _required_string(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"P1 review artifact {field_name} is missing")
    return value.strip()


def _required_sha256(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_string(payload, field_name)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"P1 review artifact {field_name} must be lowercase SHA-256")
    return value


def _hash_payload(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
