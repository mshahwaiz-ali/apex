"""JSON and SQLite persistence for frozen V2 baseline reports."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from apex.baseline.contracts import BaselineEvaluationReport
from apex.baseline.evaluation import baseline_report_to_payload

BASELINE_REPORT_SCHEMA_VERSION = 1
BASELINE_REPORT_DB_SCHEMA_VERSION = 1


def write_baseline_report(
    path: str | Path,
    report: BaselineEvaluationReport,
    *,
    force: