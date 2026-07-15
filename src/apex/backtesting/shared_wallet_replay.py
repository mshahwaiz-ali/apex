"""Deterministic shared-wallet scheduling for historical futures replay."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from apex.backtesting.contracts import SimulatedTrade


class WalletRejectionCode(StrEnum):
    """Stable reasons why an otherwise valid historical plan was not admitted."