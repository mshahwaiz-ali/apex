"""Focused tests for reproducible baseline dataset and report workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TypedDict, cast

import pytest

from apex.application.backtest_comparison import compare_backtest_reports
from apex.application.backtest_report_io import (
    BACKTEST_CAMPAIGN_DB