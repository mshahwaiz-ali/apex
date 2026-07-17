"""Canonical public serialization for Stage 3 discovery commands."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import apex.application.decision_analysis as _decision
from apex.application.discovery_contracts import ScanResult

_LEGACY_PUBLIC_KEYS = frozenset({"precision_entry", "near_miss_state"