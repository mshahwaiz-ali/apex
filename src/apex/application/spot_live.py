"""Live public-data adapter for canonical spot orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
import json

from pydantic import BaseModel, ConfigDict, Field

from apex.application.spot_analysis import SpotAnalysisResult
from apex.application.spot_orchestration import (
    SpotOrchestrationInput,
    SpotSetupEvidence,
   