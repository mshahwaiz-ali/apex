"""Persistent deterministic state for account-policy enforcement."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain import AccountPolicyState

ACCOUNT_STATE_SCHEMA_VERSION = 1


class AccountStateSnapshot(BaseModel):
    """Serializable account state used to evaluate account-policy lockouts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=ACCOUNT_STATE_SCHEMA_VERSION, ge=1)
    policy_name: str = Field(min_length=1)
    trading_day: date
    current_balance: float = Field(gt=0)
    current_equity: float = Field(gt=0)
    start_of_day_equity: float = Field(gt=0)
    trades_today: int = Field(default=0, ge=0)
    consecutive_losses: int = Field(default=0, ge=0)
    total_open_risk_pct: float = Field(default=0.0, ge=0, le=100)
    directional_exposure_pct: float = Field(default=0.0, ge=0, le=100)
    correlated_exposure_pct: float = Field(default=0.0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_exposure_geometry(self) -> Self:
        if self.directional_exposure_pct > self.total_open_risk_pct:
            raise ValueError("directional exposure cannot exceed total open risk")
        if self.correlated_exposure_pct > self.total_open_risk_pct:
            raise ValueError("correlated exposure cannot exceed total open risk")
        return self

    def _validated_update(self, **updates: Any) -> Self:
        values = self.model_dump(mode="python")
        values.update(updates)
        return type(self).model_validate(values)

    def for_policy_evaluation(
        self,
        *,
        proposed_risk_pct: float,
        proposed_has_stop_loss: bool,
        is_weekend: bool = False,
        session: str | None = None,
    ) -> AccountPolicyState:
        """Build the validated policy-state contract for a proposed setup."""

        return AccountPolicyState(
            current_balance=self.current_balance,
            current_equity=self.current_equity,
            start_of_day_equity=self.start_of_day_equity,
            trades_today=self.trades_today,
            consecutive_losses=self.consecutive_losses,
            total_open_risk_pct=self.total_open_risk_pct,
            directional_exposure_pct=self.directional_exposure_pct,
            correlated_exposure_pct=self.correlated_exposure_pct,
            is_weekend=is_weekend,
            session=session,
            proposed_risk_pct=proposed_risk_pct,
            proposed_has_stop_loss=proposed_has_stop_loss,
        )

    def roll_to_day(self, trading_day: date) -> Self:
        """Reset daily counters when the requested trading day advances."""

        if trading_day < self.trading_day:
            raise ValueError("account state cannot roll backward to an earlier trading day")
        if trading_day == self.trading_day:
            return self
        return self._validated_update(
            trading_day=trading_day,
            start_of_day_equity=self.current_equity,
            trades_today=0,
        )

    def register_entry(
        self,
        *,
        risk_pct: float,
        directional_risk_pct: float,
        correlated_risk_pct: float,
    ) -> Self:
        """Record one newly opened position after policy approval."""

        if min(risk_pct, directional_risk_pct, correlated_risk_pct) < 0:
            raise ValueError("registered exposure percentages cannot be negative")
        return self._validated_update(
            trades_today=self.trades_today + 1,
            total_open_risk_pct=self.total_open_risk_pct + risk_pct,
            directional_exposure_pct=(
                self.directional_exposure_pct + directional_risk_pct
            ),
            correlated_exposure_pct=(
                self.correlated_exposure_pct + correlated_risk_pct
            ),
        )

    def register_close(
        self,
        *,
        realized_pnl: float,
        released_risk_pct: float,
        released_directional_risk_pct: float,
        released_correlated_risk_pct: float,
        current_equity: float,
    ) -> Self:
        """Record a closed position and update loss streak and open exposure."""

        if current_equity <= 0:
            raise ValueError("current equity must remain greater than zero")
        if min(
            released_risk_pct,
            released_directional_risk_pct,
            released_correlated_risk_pct,
        ) < 0:
            raise ValueError("released exposure percentages cannot be negative")
        return self._validated_update(
            current_balance=self.current_balance + realized_pnl,
            current_equity=current_equity,
            consecutive_losses=(self.consecutive_losses + 1 if realized_pnl < 0 else 0),
            total_open_risk_pct=max(0.0, self.total_open_risk_pct - released_risk_pct),
            directional_exposure_pct=max(
                0.0,
                self.directional_exposure_pct - released_directional_risk_pct,
            ),
            correlated_exposure_pct=max(
                0.0,
                self.correlated_exposure_pct - released_correlated_risk_pct,
            ),
        )


class AccountStateStore:
    """Atomic JSON persistence for one account-state snapshot."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> AccountStateSnapshot | None:
        if not self.path.exists():
            return None
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return AccountStateSnapshot.model_validate(raw)

    def save(self, snapshot: AccountStateSnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(snapshot.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
