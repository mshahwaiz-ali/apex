"""Canonical manual trade-management contracts for futures plans.

The models in this module are provider-independent and deliberately separate
instructions from lifecycle state. They validate direction-aware geometry,
allocation arithmetic, and action consistency before any instruction is
serialized or shown to a user.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic