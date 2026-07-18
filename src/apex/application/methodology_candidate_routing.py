"""Apply methodology strategy decisions to generated candidates before ranking."""

from __future__ import annotations

from dataclasses import dataclass, replace

from apex.application.methodology_adapters import strategy_evidence_observations
from apex.application.methodology_selected_strategy_gate import MethodologyGateMode
from apex.application.methodology_strategy_contracts import