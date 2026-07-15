"""Canonical artifact-to-approval evidence bundle integration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class BundleEvidenceQuality(StrEnum):
    VALIDATED_OUT_OF_SAMPLE = "VALIDATED_OUT_OF_SAMPLE"
    VALIDATED_FORWARD_PAPER = "VALIDATED_FORWARD_PAPER"


class Bundle