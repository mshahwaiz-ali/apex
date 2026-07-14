"""Deterministic no-lookahead historical signal generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from apex.application.analysis import analyze_symbol, serialize_symbol_analysis
from apex.backtesting.dataset import FuturesCandleDataset, load_futures_dataset
from apex.backtesting.dataset_campaign import