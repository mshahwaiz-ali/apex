"""Verified provider-limit presets for funded-account readiness."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DrawdownModel(StrEnum):
    """Supported externally imposed funded-account drawdown models."""

    STATIC = "STATIC"
    TRAILING