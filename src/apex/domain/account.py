"""Account-policy contracts kept separate from trading risk modes."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AccountPolicyType(StrEnum):
    """Supported account-policy families."""

    PERSONAL = "PERSONAL"
    FUNDED = "FUNDED"
    PAPER = "PAPER"


class AccountLockoutReason(StrEnum):
    """