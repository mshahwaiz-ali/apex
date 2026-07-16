"""Seal P1 review reports with reproducible source provenance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, cast

from apex.paper_trading.forward_review import load_and_verify_forward_paper_review_report

P1_REVIEW_ARTIFACT_SCHEMA_VERSION = 1

__all__ = [
    "P1_REVIEW_ARTIFACT_SCHEMA_VERSION",
    "build_p1_review_artifact",
    "load