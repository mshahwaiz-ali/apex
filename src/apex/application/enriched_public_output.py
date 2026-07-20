"""Truthful public-output facade shared by scan and selected-symbol analysis."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from apex.application import public_output as _base
from apex.application.decision_analysis import DEFAULT_SCAN_DISPLAY_LIMIT
from apex.application.discovery_contracts import ScanResult, SymbolAnalysis
from apex.application.methodology_projection import project_analysis_methodology
from