"""Explicit file-backed regime history for live and historical parity."""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

REGIME_HISTORY_SCHEMA_VERSION = 1
REGIME_HISTORY_MAX_OBSERVATIONS_PER_SYMBOL = 512


@dataclass(frozen=True, slots=True)
class RegimeObservation:
    symbol: str
    observed_at: datetime
    raw_state: str
    selected_state: str
    probability: float

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.raw_state.strip() or not self.selected_state.strip():
            raise ValueError("regime observation text fields cannot be empty")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("regime observation timestamp must be timezone-aware")
        if not math.isfinite(self.probability) or not 0.0 <= self.probability <= 1.0:
            raise ValueError("regime observation probability must be in the unit interval")

    def as_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        return payload


class RegimeHistoryStore:
    """Persist bounded state explicitly; no module-level mutable state is used."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def observations(self, symbol: str) -> tuple[RegimeObservation, ...]:
        payload = self._read()
        records = payload.get("observations", {})
        if not isinstance(records, dict):
            raise ValueError("regime history observations must be an object")
        raw_values = records.get(symbol.upper(), [])
        if not isinstance(raw_values, list):
            raise ValueError("regime history symbol observations must be a list")
        parsed = tuple(_observation_from_payload(value) for value in raw_values)
        if tuple(sorted(parsed, key=lambda item: item.observed_at)) != parsed:
            raise ValueError("regime history observations must be chronological")
        return parsed

    def previous_state(self, symbol: str, *, before: datetime) -> str | None:
        if before.tzinfo is None or before.utcoffset() is None:
            raise ValueError("regime history lookup timestamp must be timezone-aware")
        eligible = tuple(item for item in self.observations(symbol) if item.observed_at < before)
        return eligible[-1].selected_state if eligible else None

    def append(self, observation: RegimeObservation) -> None:
        payload = self._read()
        records = payload.setdefault("observations", {})
        if not isinstance(records, dict):
            raise ValueError("regime history observations must be an object")
        symbol = observation.symbol.upper()
        current = self.observations(symbol)
        without_duplicate = tuple(
            item for item in current if item.observed_at != observation.observed_at
        )
        updated = tuple(
            sorted((*without_duplicate, observation), key=lambda item: item.observed_at)
        )[-REGIME_HISTORY_MAX_OBSERVATIONS_PER_SYMBOL:]
        records[symbol] = [item.as_payload() for item in updated]
        payload["schema_version"] = REGIME_HISTORY_SCHEMA_VERSION
        self._write(payload)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": REGIME_HISTORY_SCHEMA_VERSION,
                "observations": {},
            }
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("regime history root must be an object")
        if payload.get("schema_version") != REGIME_HISTORY_SCHEMA_VERSION:
            raise ValueError("unsupported regime history schema version")
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".part")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)


def regime_observation_from_analysis(
    *,
    symbol: str,
    observed_at: datetime,
    market_intelligence: Mapping[str, object] | None,
) -> RegimeObservation | None:
    if not isinstance(market_intelligence, Mapping):
        return None
    regime = market_intelligence.get("regime")
    if not isinstance(regime, Mapping):
        return None
    raw_state = regime.get("raw_state")
    selected_state = regime.get("state")
    probability = regime.get("probability")
    if (
        not isinstance(raw_state, str)
        or not isinstance(selected_state, str)
        or not isinstance(probability, (int, float))
    ):
        return None
    return RegimeObservation(
        symbol=symbol.upper(),
        observed_at=observed_at,
        raw_state=raw_state,
        selected_state=selected_state,
        probability=float(probability),
    )


def _observation_from_payload(payload: object) -> RegimeObservation:
    if not isinstance(payload, dict):
        raise ValueError("regime observation must be an object")
    return RegimeObservation(
        symbol=str(payload["symbol"]),
        observed_at=datetime.fromisoformat(str(payload["observed_at"])),
        raw_state=str(payload["raw_state"]),
        selected_state=str(payload["selected_state"]),
        probability=float(payload["probability"]),
    )


__all__ = [
    "REGIME_HISTORY_MAX_OBSERVATIONS_PER_SYMBOL",
    "REGIME_HISTORY_SCHEMA_VERSION",
    "RegimeHistoryStore",
    "RegimeObservation",
    "regime_observation_from_analysis",
]
