"""Deterministic P1 deviation, lifecycle-audit, and review artifacts."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from apex.paper_trading.contracts import PaperTrade, PaperTradeState, TERMINAL_STATES
