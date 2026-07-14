"""Forward-paper evidence evaluation for setup-specific historical edges."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import fmean
from types import MappingProxyType

from apex.backtesting import (
    DEFAULT_EDGE_SEGMENTS,
    EvidenceQuality,
    HistoricalEdgeValidationResult,
    HistoricalEdgeValidation