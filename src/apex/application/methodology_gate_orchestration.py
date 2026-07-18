"""Apply configured methodology enforcement to one completed symbol analysis."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.methodology_projection import project_analysis_methodology
from apex.application.methodology_selected_strategy_gate import (
    MethodologyGateMode,
    apply_selected_strategy_gate,