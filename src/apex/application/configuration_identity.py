"""Deterministic configuration identity for discovery records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, cast

CONFIGURATION_SCHEMA_VERSION = 1


def configuration_metadata(configuration: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable versioned configuration snapshot and identifier."""

    snapshot = _json_roundtrip(configuration)
    encoded = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    configuration_hash = hashlib.sha256(encoded).