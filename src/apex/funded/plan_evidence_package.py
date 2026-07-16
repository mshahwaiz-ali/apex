"""Immutable funded-plan evidence packages with deterministic verification."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, TypeAdapter

from apex.funded.plan_eligibility import FundedPlanEligibility
from apex.funded.provider_policy_binding import