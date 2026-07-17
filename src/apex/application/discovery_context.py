"""Discovery-neutral market context construction and data-quality reporting."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from apex.config import DEFAULT_TIMEFRAME_ROLES
from apex.config.settings import DEFAULT_TIMEFRAME_MAX_STALENESS_SECONDS
from apex.data.providers.base import MarketDataProvider
from apex.domain.models import (
