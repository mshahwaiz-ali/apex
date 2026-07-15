"""Deterministic shared-wallet scheduling for historical futures replay."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.backtesting.contracts import SimulatedTrade


class WalletRejectionCode(StrEnum):
    """Stable reasons why a valid historical plan was not admitted."""

    CAMPAIGN_PAUSED = "campaign_paused"
    CONCURRENCY_LIMIT = "maximum_concurrent_positions"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    DUPLICATE_SYMBOL = "overlapping_symbol_position"
    EXPOSURE_LIMIT = "maximum_wallet_exposure"
    INSUFFICIENT_MARGIN = "insufficient_available_margin"
    LOSS_LOCKOUT = "consecutive_loss_lockout"


@dataclass(frozen=True, slots=True)
class SharedWalletConfig:
    """Account constraints applied to one chronological replay timeline."""

    maximum_concurrent_positions: int = 3
    maximum_wallet_exposure_pct: float = 50.0
    daily_loss_limit_pct: float = 10.0
    consecutive_loss_limit: int = 4

    def __post_init__(self) -> None:
        if self.maximum_concurrent_positions < 1:
            raise ValueError("maximum concurrent positions must be positive")
        if self.consecutive_loss_limit < 1:
            raise ValueError("consecutive loss limit must be positive")
        for name, value in (
            ("maximum wallet exposure percentage", self.maximum_wallet_exposure_pct),
            ("daily loss limit percentage", self.daily_loss_limit_pct),
        ):
            if not math.isfinite(value) or not 0.0 < value <= 100.0:
                raise ValueError(f"{name} must be finite and in (0, 100]")

    def to_payload(self) -> dict[str, object]:
        return {
            "maximum_concurrent_positions": self.maximum_concurrent_positions,
            "maximum_wallet_exposure_pct": self.maximum_wallet_exposure_pct,
            "daily_loss_limit_pct": self.daily_loss_limit_pct,
            "consecutive_loss_limit": self.consecutive_loss_limit,
        }


@dataclass(frozen=True, slots=True)
class WalletReplayCandidate:
    """A simulated trade plus account resources required at admission."""

    candidate_id: str
    split: str
    trade: SimulatedTrade
    required_margin: float

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.split.strip():
            raise ValueError("wallet replay candidate identifiers cannot be empty")
        if not math.isfinite(self.required_margin) or self.required_margin <= 0.0:
            raise ValueError("required margin must be positive and finite")


@dataclass(frozen=True, slots=True)
class WalletReplayDecision:
    """Admission outcome for one candidate."""

    candidate_id: str
    accepted: bool
    rejection_code: WalletRejectionCode | None
    equity: float
    available_balance: float
    reserved_margin: float


@dataclass(frozen=True, slots=True)
class WalletEquityPoint:
    """One deterministic realized-equity observation."""

    timestamp: datetime
    equity: float
    available_balance: float
    reserved_margin: float
    open_positions: int
    event: str
    candidate_id: str

    def to_payload(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": self.equity,
            "available_balance": self.available_balance,
            "reserved_margin": self.reserved_margin,
            "open_positions": self.open_positions,
            "event": self.event,
            "candidate_id": self.candidate_id,
        }


@dataclass(frozen=True, slots=True)
class SharedWalletReplayResult:
    """Completed shared-wallet replay state."""

    starting_equity: float
    ending_equity: float
    peak_equity: float
    maximum_drawdown: float
    realized_pnl: float
    total_fees: float
    decisions: tuple[WalletReplayDecision, ...]
    accepted_candidates: tuple[WalletReplayCandidate, ...]
    equity_curve: tuple[WalletEquityPoint, ...]
    rejection_counts: tuple[tuple[str, int], ...]


def replay_shared_wallet(
    *,
    candidates: tuple[WalletReplayCandidate, ...],
    starting_equity: float,
    config: SharedWalletConfig,
) -> SharedWalletReplayResult:
    """Admit pre-simulated trades onto one chronological shared account timeline."""

    if not math.isfinite(starting_equity) or starting_equity <= 0.0:
        raise ValueError("shared wallet starting equity must be positive and finite")
    ordered = tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.trade.signal.generated_at,
                item.trade.signal.symbol,
                item.candidate_id,
            ),
        )
    )
    if len({item.candidate_id for item in ordered}) != len(ordered):
        raise ValueError("wallet replay candidate IDs must be unique")

    equity = starting_equity
    peak_equity = starting_equity
    maximum_drawdown = 0.0
    reserved_margin = 0.0
    consecutive_losses = 0
    current_day = None
    day_start_equity = starting_equity
    paused_day = None
    open_positions: list[WalletReplayCandidate] = []
    decisions: list[WalletReplayDecision] = []
    accepted: list[WalletReplayCandidate] = []
    curve: list[WalletEquityPoint] = []
    rejections: Counter[str] = Counter()

    def close_due(through: datetime) -> None:
        nonlocal equity, peak_equity, maximum_drawdown, reserved_margin, consecutive_losses
        due = sorted(
            (item for item in open_positions if item.trade.exit_time <= through),
            key=lambda item: (item.trade.exit_time, item.candidate_id),
        )
        for item in due:
            reserved_margin -= item.required_margin
            equity += item.trade.net_pnl
            peak_equity = max(peak_equity, equity)
            maximum_drawdown = max(
                maximum_drawdown,
                (peak_equity - equity) / peak_equity if peak_equity else 0.0,
            )
            consecutive_losses = consecutive_losses + 1 if item.trade.net_pnl < 0.0 else 0
            open_positions.remove(item)
            curve.append(
                WalletEquityPoint(
                    timestamp=item.trade.exit_time,
                    equity=equity,
                    available_balance=equity - reserved_margin,
                    reserved_margin=reserved_margin,
                    open_positions=len(open_positions),
                    event="closed",
                    candidate_id=item.candidate_id,
                )
            )

    for item in ordered:
        decision_time = item.trade.signal.generated_at
        close_due(decision_time)
        decision_day = decision_time.date()
        if current_day != decision_day:
            current_day = decision_day
            day_start_equity = equity
            paused_day = None

        rejection: WalletRejectionCode | None = None
        if paused_day == decision_day:
            rejection = WalletRejectionCode.CAMPAIGN_PAUSED
        elif len(open_positions) >= config.maximum_concurrent_positions:
            rejection = WalletRejectionCode.CONCURRENCY_LIMIT
        elif any(open_item.trade.signal.symbol == item.trade.signal.symbol for open_item in open_positions):
            rejection = WalletRejectionCode.DUPLICATE_SYMBOL
        elif consecutive_losses >= config.consecutive_loss_limit:
            paused_day = decision_day
            rejection = WalletRejectionCode.LOSS_LOCKOUT
        elif day_start_equity - equity >= day_start_equity * config.daily_loss_limit_pct / 100.0:
            paused_day = decision_day
            rejection = WalletRejectionCode.DAILY_LOSS_LIMIT
        elif item.required_margin > equity - reserved_margin:
            rejection = WalletRejectionCode.INSUFFICIENT_MARGIN
        elif (reserved_margin + item.required_margin) / equity * 100.0 > config.maximum_wallet_exposure_pct:
            rejection = WalletRejectionCode.EXPOSURE_LIMIT

        decisions.append(
            WalletReplayDecision(
                candidate_id=item.candidate_id,
                accepted=rejection is None,
                rejection_code=rejection,
                equity=equity,
                available_balance=equity - reserved_margin,
                reserved_margin=reserved_margin,
            )
        )
        if rejection is not None:
            rejections[rejection.value] += 1
            continue
        reserved_margin += item.required_margin
        open_positions.append(item)
        accepted.append(item)
        curve.append(
            WalletEquityPoint(
                timestamp=decision_time,
                equity=equity,
                available_balance=equity - reserved_margin,
                reserved_margin=reserved_margin,
                open_positions=len(open_positions),
                event="opened",
                candidate_id=item.candidate_id,
            )
        )

    for item in sorted(open_positions, key=lambda value: (value.trade.exit_time, value.candidate_id)):
        close_due(item.trade.exit_time)

    return SharedWalletReplayResult(
        starting_equity=starting_equity,
        ending_equity=equity,
        peak_equity=peak_equity,
        maximum_drawdown=maximum_drawdown,
        realized_pnl=equity - starting_equity,
        total_fees=sum(item.trade.fees for item in accepted),
        decisions=tuple(decisions),
        accepted_candidates=tuple(accepted),
        equity_curve=tuple(curve),
        rejection_counts=tuple(sorted(rejections.items())),
    )
