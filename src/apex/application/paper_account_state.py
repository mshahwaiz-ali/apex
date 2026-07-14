"""Synchronize persistent account state with paper-trade lifecycle changes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.account_state import AccountStateSnapshot
from apex.paper_trading import PaperTrade, TERMINAL_STATES

ACCOUNT_STATE_REGISTRATION_KEY = "account_state_registration"


@dataclass(frozen=True, slots=True)
class PaperAccountExposure:
    """Explicit exposure metadata preserved with an approved paper plan."""

    policy_name: str
    risk_pct: float
    directional_risk_pct: float = 0.0
    correlated_risk_pct: float = 0.0

    def __post_init__(self) -> None:
        if not self.policy_name.strip():
            raise ValueError("paper account exposure requires a policy name")
        if min(self.risk_pct, self.directional_risk_pct, self.correlated_risk_pct) < 0.0:
            raise ValueError("paper account exposure percentages cannot be negative")
        if self.directional_risk_pct > self.risk_pct:
            raise ValueError("directional paper exposure cannot exceed total risk")
        if self.correlated_risk_pct > self.risk_pct:
            raise ValueError("correlated paper exposure cannot exceed total risk")

    def as_plan_metadata(self) -> dict[str, object]:
        """Serialize exposure metadata into an approved futures plan."""

        return {
            "policy_name": self.policy_name,
            "risk_pct": self.risk_pct,
            "directional_risk_pct": self.directional_risk_pct,
            "correlated_risk_pct": self.correlated_risk_pct,
        }


def attach_account_state_registration(
    futures_plan: dict[str, object],
    exposure: PaperAccountExposure,
) -> dict[str, object]:
    """Return a plan copy carrying deterministic account-state registration metadata."""

    return futures_plan | {ACCOUNT_STATE_REGISTRATION_KEY: exposure.as_plan_metadata()}


def apply_paper_account_transition(
    snapshot: AccountStateSnapshot,
    before: PaperTrade,
    after: PaperTrade,
) -> AccountStateSnapshot:
    """Apply one paper lifecycle transition to persistent account state."""

    exposure = _exposure_from_trade(after)
    if exposure is None:
        return snapshot
    if exposure.policy_name != snapshot.policy_name:
        raise ValueError("paper trade account policy does not match account-state policy")

    updated = snapshot
    entered_now = before.entry_time is None and after.entry_time is not None
    if entered_now:
        updated = updated.register_entry(
            risk_pct=exposure.risk_pct,
            directional_risk_pct=exposure.directional_risk_pct,
            correlated_risk_pct=exposure.correlated_risk_pct,
        )

    if after.entry_time is None:
        return updated

    terminal_now = before.state not in TERMINAL_STATES and after.state in TERMINAL_STATES
    if terminal_now:
        remaining_fraction = max(0.0, 100.0 - before.closed_percentage) / 100.0
        return updated.register_close(
            realized_pnl=after.net_pnl,
            released_risk_pct=exposure.risk_pct * remaining_fraction,
            released_directional_risk_pct=(
                exposure.directional_risk_pct * remaining_fraction
            ),
            released_correlated_risk_pct=(
                exposure.correlated_risk_pct * remaining_fraction
            ),
            current_equity=updated.current_equity + after.net_pnl,
        )

    newly_closed = max(0.0, after.closed_percentage - before.closed_percentage)
    if newly_closed > 0.0:
        release_fraction = newly_closed / 100.0
        updated = updated.release_exposure(
            released_risk_pct=exposure.risk_pct * release_fraction,
            released_directional_risk_pct=(
                exposure.directional_risk_pct * release_fraction
            ),
            released_correlated_risk_pct=(
                exposure.correlated_risk_pct * release_fraction
            ),
        )
    return updated


def _exposure_from_trade(trade: PaperTrade) -> PaperAccountExposure | None:
    plan = trade.futures_plan
    if plan is None:
        return None
    raw = plan.get(ACCOUNT_STATE_REGISTRATION_KEY)
    if not isinstance(raw, dict):
        return None
    return PaperAccountExposure(
        policy_name=_required_string(raw, "policy_name"),
        risk_pct=_required_float(raw, "risk_pct"),
        directional_risk_pct=_optional_float(raw, "directional_risk_pct"),
        correlated_risk_pct=_optional_float(raw, "correlated_risk_pct"),
    )


def _required_string(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"paper account metadata requires {key}")
    return value


def _required_float(raw: dict[str, Any], key: str) -> float:
    value = raw.get(key)
    if not isinstance(value, int | float):
        raise ValueError(f"paper account metadata requires numeric {key}")
    return float(value)


def _optional_float(raw: dict[str, Any], key: str) -> float:
    value = raw.get(key, 0.0)
    if not isinstance(value, int | float):
        raise ValueError(f"paper account metadata requires numeric {key}")
    return float(value)
