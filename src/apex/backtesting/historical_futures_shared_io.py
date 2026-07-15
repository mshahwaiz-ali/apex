"""Atomic persistence helpers for shared historical futures artifacts."""

from __future__ import annotations

import hashlib
import json
from contextlib import suppress
from pathlib import Path


def write_shared_artifacts(
    *,
    result_path: Path,
    manifest_path: Path,
    result_payload: dict[str, object],
    manifest_payload: dict[str, object],
    expected_result_hash: str,
) -> None:
    """Write result and manifest atomically and verify both after reload."""

    if result_path.resolve(strict=False) == manifest_path.resolve(strict=False):
        raise ValueError("shared historical futures artifact paths must be unique")
    for path in (result_path, manifest_path):
        if path.exists():
            raise FileExistsError(f"shared historical futures campaign refuses to overwrite: {path}")

    created: list[Path] = []
    temporary: list[Path] = []
    try:
        _atomic_json_write(result_path, result_payload, created, temporary)
        reloaded_result = _load_object(result_path, label="shared historical futures result")
        if _hash_json(reloaded_result) != expected_result_hash:
            raise ValueError("shared historical futures result hash changed after reload")

        _atomic_json_write(manifest_path, manifest_payload, created, temporary)
        reloaded_manifest = _load_object(
            manifest_path,
            label="shared historical futures execution manifest",
        )
        if reloaded_manifest != manifest_payload:
            raise ValueError("shared historical futures manifest changed after reload")
        if reloaded_manifest.get("result_hash") != expected_result_hash:
            raise ValueError("shared historical futures manifest result hash mismatch")
    except Exception:
        for path in reversed(created):
            with suppress(OSError):
                path.unlink(missing_ok=True)
        raise
    finally:
        for path in temporary:
            with suppress(OSError):
                path.unlink(missing_ok=True)


def hash_json(value: object) -> str:
    """Return the canonical SHA-256 digest for a JSON-compatible value."""

    return _hash_json(value)


def _atomic_json_write(
    path: Path,
    payload: object,
    created: list[Path],
    temporary: list[Path],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temporary.append(temp)
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)
    created.append(path)


def _load_object(path: Path, *, label: str) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _hash_json(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
