"""Validate N4.8 futures edge reports across train, validation, and final-test splits."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from apex.backtesting.historical_edge import EvidenceQuality, HistoricalEdgeProfile
from apex.backtesting.historical_edge_validation import