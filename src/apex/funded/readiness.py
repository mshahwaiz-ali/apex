"""Deterministic funded-account readiness contracts and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from apex.domain import AccountPolicyDecision, AccountPolicyType, RiskMode
from apex.execution.contracts import KillSwitchState

if TYPE_CHECKING:
    from apex.validation import AggregateHistoryReport, ForwardValidationReport


class FundedReadinessReason(Str