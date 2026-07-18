"""Interpret target feasibility without imposing a universal reward threshold."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_contracts import TargetCandidate
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class TargetFeasibilityItem:
    """Derived geometry for one canonical target candidate."""