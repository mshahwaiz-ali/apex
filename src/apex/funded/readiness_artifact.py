"""Seal funded-readiness reports with exact input provenance."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

FUNDED_READINESS_ARTIFACT_SCHEMA_VERSION = 1

__all__ = [
    "FUNDED_READINESS_ARTIFACT_SCHEMA_VERSION",
    "build_funded_readiness_artifact",
    "load_and_verify_funded_readiness_artifact",
    "write_funded_readiness_artifact",
]


def build_funded_readiness_artifact