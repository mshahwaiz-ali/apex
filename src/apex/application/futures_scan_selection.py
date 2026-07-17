"""Resolve symbols for one futures scan execution."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from apex.application.futures_screening import (
    screen_futures_universe,
    ticker_prefilter_symbols,
)
from apex.application.futures_universe import filter_futures_universe
from apex.application.symbols import load_symbol_file
from apex.data.providers.base import (
    Futures