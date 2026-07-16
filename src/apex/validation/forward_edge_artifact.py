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