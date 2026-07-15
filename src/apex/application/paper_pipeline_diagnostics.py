"""Stable diagnostic aggregation for futures scans and paper pipelines."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from apex.application.analysis import ScanResult, SymbolAnalysis

_ACCEPTED_OUTCOMES = frozenset({"accepted", "accepted_with_conflict_warning"})
_REJECTED