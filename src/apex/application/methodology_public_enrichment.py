"""Build truthful methodology metadata for public discovery output."""

from __future__ import annotations

from typing import Any

from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.methodology_actionability_semantics import (
    actionability_semantics_payload,
    derive_actionability_semantics,
)
from apex.application.method