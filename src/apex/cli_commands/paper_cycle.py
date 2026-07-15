"""Provider-backed P1 paper-operation CLI command."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import typer

from apex.application import bootstrap, create_market_data_services
from apex.paper_trading import (
    PaperRuntimeResult,
    PaperTradeConfig,
    PaperTradeStore,
    run_provider_backed_paper_cycle,
    write