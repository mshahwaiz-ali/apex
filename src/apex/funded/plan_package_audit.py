"""Read-only audit summaries and deterministic indexes for funded-plan packages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from apex.funded.plan_evidence_package import (
    FundedPlanEvidencePackage,
    canonical_sha256,
    load_and_verify_funded_plan_evidence_package,
)

__all__ = [
    "FUNDED_PLAN_A