"""Deterministic configuration identity for discovery records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, cast

from apex.application.methodology_identity import methodology_identity_payload
from apex.application.quality_contracts import (
    ParameterProvenance,
    ResolvedParameter,
)

CONFIGURATION_SCHEMA_VERSION = 2
PARAMETER_RESOLUTION_VERSION = "quality-recovery-v1"


def configuration_metadata(configuration: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable versioned configuration snapshot and identifier."""

    snapshot = _json_roundtrip(configuration)
    encoded = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    configuration_hash = hashlib.sha256(encoded).hexdigest()
    return {
        "configuration_schema_version": CONFIGURATION_SCHEMA_VERSION,
        "configuration_id": configuration_hash,
        "configuration_hash": configuration_hash,
        "configuration": snapshot,
        "methodology_identity": methodology_identity_payload(),
        "resolved_parameters": [
            item.as_payload() for item in resolved_configuration_parameters(snapshot)
        ],
    }


def resolved_configuration_parameters(
    configuration: Mapping[str, Any],
) -> tuple[ResolvedParameter, ...]:
    """Expose every resolved leaf with explicit current-value provenance."""

    resolved: list[ResolvedParameter] = []

    def visit(prefix: str, value: object) -> None:
        if isinstance(value, Mapping):
            for key in sorted(value):
                name = f"{prefix}.{key}" if prefix else str(key)
                visit(name, value[key])
            return
        resolved.append(
            ResolvedParameter(
                name=prefix,
                base_value=value,
                adjustment_factors=(),
                final_value=value,
                units=_parameter_units(prefix),
                provenance=ParameterProvenance.EXISTING_PRODUCTION_VALUE,
                bounds=None,
                version=PARAMETER_RESOLUTION_VERSION,
                reason="resolved from validated production configuration without adaptation",
            )
        )

    visit("", configuration)
    return tuple(resolved)


def _parameter_units(name: str) -> str:
    if name.endswith(("_pct", "_percentage")):
        return "percentage_points"
    if name.endswith("_seconds"):
        return "seconds"
    if name.endswith(("_size", "_limit", "_count", "_period", "_lookback")):
        return "count"
    if name.endswith(("_weights", "_score")):
        return "score_units"
    return "configured_units"


def _json_roundtrip(configuration: Mapping[str, Any]) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(json.dumps(configuration, sort_keys=True, default=str)),
    )


__all__ = [
    "CONFIGURATION_SCHEMA_VERSION",
    "PARAMETER_RESOLUTION_VERSION",
    "configuration_metadata",
    "resolved_configuration_parameters",
]
