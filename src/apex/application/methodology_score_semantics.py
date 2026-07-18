"""Interpret discovery scores without turning them into probability or gate repair."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class ScoreSemantics:
    """Transparent interpretation of legacy and methodology scoring