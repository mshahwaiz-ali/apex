"""Atomic persistence for shared-wallet historical futures campaign artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from apex.application.historical_signal_io import load_historical_signal_execution_manifest
from apex.backtesting.historical_futures_campaign import (
    Historical