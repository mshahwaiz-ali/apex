"""Deterministic persistence for historical signal-generation results."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apex.application.historical_signal_generation import (
    HistoricalSignalGenerationResult,
    HistoricalSignalRecord,
)
from apex