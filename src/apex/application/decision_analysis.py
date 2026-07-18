"""Canonical strategy-routing analysis orchestration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from apex.application import integrated_analysis as _integrated
from apex.application.discovery_contracts import (
    ScanResult as DiscoveryScanResult,
    SymbolAnalysis as Discovery