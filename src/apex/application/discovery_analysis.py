"""Discovery-neutral analysis orchestration for live scan and analyze flows."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apex.application import analysis as _legacy
from apex.application.candidate_ranking import (
    build_candidate_ranking_snapshot,
    candidate_ranking_payload,
)
from apex.application.discovery_contracts import ScanResult,