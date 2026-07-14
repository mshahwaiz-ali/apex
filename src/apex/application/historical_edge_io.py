"""Deterministic report serialization and SQLite storage for historical edge."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from apex.application.backtest_report_io import dumps_report, to_json_value
from apex.application.historical_edge import (
    DatasetPartition,
    DatasetSplit,
   