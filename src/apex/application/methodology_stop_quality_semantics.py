"""Interpret stop placement quality without inventing arbitrary thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_contracts import EntryOpportunity, StructuralInvalidation
from apex.application.methodology_snapshot import MethodologySnapshot

