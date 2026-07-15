"""Stable Phase 5 scoring and selection diagnostics for futures scan runs."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from apex.application.analysis import SymbolAnalysis

_ACCEPTED_OUTCOMES = frozenset({"accepted", "accepted_with_conflict_warning"})
_REJECTED