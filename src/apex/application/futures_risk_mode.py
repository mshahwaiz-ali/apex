"""Scoped futures risk-mode selection for N3 orchestration."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from apex.domain import RiskMode

_ACTIVE_FUTURES_RISK_MODE: ContextVar[RiskMode] = ContextVar(
    "active_futures_risk_mode",
    default=RiskMode.STANDARD,
)


def current_futures_risk_mode() -> RiskMode:
    """Return the risk mode selected for the current analysis execution."""

    return _ACTIVE_FUTURES_RISK_MODE.get()


@contextmanager
def futures_risk_mode_scope(risk_mode: RiskMode | str) -> Iterator[RiskMode]:
    """Temporarily select one validated futures risk mode for analysis."""

    selected = risk_mode if isinstance(risk_mode, RiskMode) else RiskMode(str(risk_mode).upper())
    token: Token[RiskMode] = _ACTIVE_FUTURES_RISK_MODE.set(selected)
    try:
        yield selected
    finally:
        _ACTIVE_FUTURES_RISK_MODE.reset(token)
