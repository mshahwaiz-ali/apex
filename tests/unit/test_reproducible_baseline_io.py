"""Focused tests for reproducible baseline dataset and report workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TypedDict

import pytest

from apex.application.backtest_comparison import compare_backtest