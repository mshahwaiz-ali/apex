"""Strict local JSON/CSV historical candle dataset loading."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from apex.application.symbols import normalize_market_symbol
from apex