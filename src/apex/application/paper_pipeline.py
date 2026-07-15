"""Scheduler-safe orchestration for paper intake followed by lifecycle advancement."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from apex.paper_tr