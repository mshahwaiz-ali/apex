"""Deterministic futures strategy approval and evidence-gated eligibility decisions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.backtesting.historical_edge import EvidenceQuality
from apex.backtesting.historical_edge_validation import (
    HistoricalEdgeValidationResult,
    HistoricalEdgeValidationStatus,
)
from apex.config.strategy_approval import StrategyApprovalConfig, StrategyQualityClass
from apex.domain import AccountPolicyDecision, EntryState, RiskMode
from apex.strategies import StrategyType


class SetupEligibility(StrEnum):
    """Operational eligibility after strategy, risk-mode, policy,