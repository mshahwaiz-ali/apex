"""Derive canonical setup maturity from legacy candidate actionability."""

from __future__ import annotations

from dataclasses import dataclass

from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    SetupMaturity,
)
from apex.application.methodology_strategy_registry import strategy_eligibility
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


@dataclass(frozen=True, slots=True)
class SetupMaturityAssessment:
    strategy: StrategyType
    legacy_status: EntryStatus
    maturity: SetupMaturity
    confirmation_policy: ConfirmationPolicy
    execution_conditions_complete: bool
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reason_codes or not self.reasons:
            raise ValueError("setup maturity assessment requires reasons")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("setup maturity reason codes must be unique")


def