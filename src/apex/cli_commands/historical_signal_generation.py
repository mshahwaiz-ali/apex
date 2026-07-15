"""CLI command for deterministic historical signal campaign generation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

import typer

from apex.historical_signals import (
    HistoricalSignalCampaignManifest,
    generate_and_persist_historical_signal_campaign,
    load_historical_signal_campaign_manifest,
    load_historical_signal_records,