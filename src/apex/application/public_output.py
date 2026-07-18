"""Canonical public serialization for Stage 3 discovery commands."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, cast

import apex.application.decision_analysis as _decision
from apex.application.discovery_contracts import ScanResult, SymbolAnalysis
from apex.application.methodology_projection import project_analysis_methodology
from apex.application.methodology_selected_strategy_verdict import (
    derive_selected_strategy_verdict,
    selected_strategy_verdict_payload,
)
from apex.application.methodology_setup_maturity import (
    Setup