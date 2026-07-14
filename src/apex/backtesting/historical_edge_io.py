"""Stable JSON and SQLite persistence for historical edge profiles."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from apex.backtesting.historical_edge import HistoricalEdgeProfile

HISTORICAL_EDGE_REPORT_SCHEMA_VERSION = 1
HISTORICAL_EDGE_DB_SCHEMA_VERSION = 1


def build