"""Operational CLI for the combined P1 forward-paper review artifact."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import typer

from apex.backtesting import EvidenceQuality, HistoricalEdgeProfile
from apex.paper_trading import (
    ForwardPaperEdgeProfile,
    ForwardPaperValidationStatus,
    PaperTradeStore,
    audit_paper_trade_l