"""Map approved risk setups into the frozen futures output contract."""

from __future__ import annotations

from pathlib import Path

from apex.config import FuturesProductConfig, load_futures_product_config
from apex.domain import (
    EntryPlan,
    EntryState,
    FuturesAccountInput,
    FuturesDirection,
    PositionPlan,
    StopPlan,
    TargetLeg,
    TargetPlan,
)
from apex.risk.contracts import RiskApprovedSetup

DEFAULT_FUTURES_CONFIG_PATH = Path("config/futures.yaml")


class FuturesPlanSafetyError(ValueError):
    """Raised when an approved market setup is unsafe for the selected account profile."""

    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def build_futures_plan(
    setup: RiskApprovedSetup,
    account: FuturesAccountInput,