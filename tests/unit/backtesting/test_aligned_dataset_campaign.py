"""Tests for timestamp-aligned historical dataset campaigns."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from apex.backtesting.aligned_dataset_campaign import (
    load_aligned_dataset_campaign_plan,
    plan_aligned_dataset_campaign,
    write_aligned_dataset_campaign_plan,
)
from apex.backtesting.aligned_dataset_campaign_execution import (