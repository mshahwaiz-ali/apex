"""Normalization and validation for user-selected market symbols."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import yaml

_SYMBOL_PART = re.compile(r"^[A-Z0-9][A-Z0-9._-]*$")
DEFAULT_QUOTE_ASSETS: tuple[str, ...] = ("USDT", "USDC", "USD", "BTC", "ETH", "BNB")


def load_symbol_file(path: str | Path) -> tuple[str, ...]:
