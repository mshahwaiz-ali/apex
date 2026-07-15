"""Deterministic P1 forward-paper daily validation reporting."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, cast

from apex.paper_trading.contracts import PaperTrade, TERMINAL_STATES

FORWARD_PAPER_DAILY_REPORT