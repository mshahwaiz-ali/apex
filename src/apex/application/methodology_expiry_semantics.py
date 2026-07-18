"""Interpret setup and entry expiry without inventing elapsed-bar state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_strategy_contracts import SetupMaturity


@dataclass(frozen=True, slots=True)
class ExpirySemantics:
    """Public interpretation of setup lifetime