"""Independent source-to-package reproduction verification for funded plans."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, TypeAdapter

from apex.funded.plan_evidence_package import (
    FundedPlanEvidencePackage,
    canonical_sha256,
    verify_funded_plan_evidence_package,
)

__all__ = [
    "FUNDED_PLAN_RE