"""Leakage-safe historical replay through the canonical spot analysis stack."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apex.application.spot_analysis import spot_analysis_result_to_payload
from apex.application.spot_historical_dataset import (
    SpotHistoricalDatasetManifest,
    hash_spot_historical_rows,
    load_spot_historical_rows,
)
from apex.application.spot_live import _evidence, _snapshot
from apex.application.spot_orchestration import SpotOrchestrationInput, analyze_spot_or