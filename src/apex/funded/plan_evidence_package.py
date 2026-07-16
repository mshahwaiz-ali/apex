"""Immutable funded-plan evidence packages with deterministic verification."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, TypeAdapter

from apex.funded.plan_eligibility import FundedPlanEligibility
from apex.funded.provider_policy_binding import ProviderPolicyBinding

__all__ = [
    "FUNDED_PLAN_PACKAGE_SCHEMA_VERSION",
    "FundedPlanEvidenceManifest",
    "FundedPlanEvidencePackage",
    "build_funded_plan_evidence_package",
    "canonical_sha256",
    "load_and_verify_funded_plan_evidence_package",
    "verify_funded_plan_evidence_package",
    "write_funded_plan_evidence_package",
]

