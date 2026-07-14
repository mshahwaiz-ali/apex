"""Derive one operational instruction from a paper trade and its canonical plan."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from apex.domain import CurrentAction
from apex.paper_trading.contracts import PaperTrade, PaperTradeState
from apex.paper_trading.engine import paper_lifecycle_snapshot
from apex.paper_trading.management import paper_entry_exp