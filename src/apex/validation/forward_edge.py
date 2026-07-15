"""Attach forward-paper evidence to validated historical setup segments."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from apex.backtesting.historical_edge import EvidenceQuality
from apex.paper_trading import PaperTrade

