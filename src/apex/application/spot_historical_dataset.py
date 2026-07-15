"""Deterministic multi-symbol historical spot dataset acquisition and manifests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apex.application.symbols import normalize_market_symbol
from apex.data.providers.base import HistoricalRangeMarketDataProvider
from apex.domain.models import Candle

SPOT_H