"""Atomic orchestration for the complete N4 historical evidence pipeline."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from apex.backtesting.historical_edge_io import write_historical_edge_report
from apex.backtesting.historical_futures_edge import build_historical_futures_edge_report
from