"""Integration coverage for persisted shared-wallet historical futures replay."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.application.historical_signal_io import HistoricalSignalExecutionManifest
from apex.backtesting import (
    BacktestConfig,
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalFuturesCampaignRequest,
    HistoricalReplay