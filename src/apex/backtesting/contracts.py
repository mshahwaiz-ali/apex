"""Immutable contracts for deterministic historical backtesting."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from apex.application.methodology_identity import METHODOLOGY_VERSION
