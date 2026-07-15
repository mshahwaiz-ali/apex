"""Tests for mapping approved setups into the futures output contract."""

from collections.abc import Mapping
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from apex.application import (
    FuturesPlanSafetyError,
    build_futures_plan,
    build_futures_plan_result,
)
from apex.domain import FuturesAccountInput, LeverageMode