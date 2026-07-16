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
    "load_and_verify_funded_history_read