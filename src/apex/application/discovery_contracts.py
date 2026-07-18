"""Discovery-neutral contracts for trade setup construction and analysis."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from apex.application.candidate_ranking import CandidateRankingSnapshot
from apex.application.methodology_snapshot import MethodologySnapshot
from apex