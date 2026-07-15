"""Deterministic P1 forward-paper daily validation reporting."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, cast

from apex.paper_trading.contracts import PaperTrade, TERMINAL_STATES

FORWARD_PAPER_DAILY_REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ForwardPaperDailyReport:
    """Immutable daily forward-paper lifecycle and performance audit."""

    payload: dict[str, Any]
    report_sha256: str


def build_forward_paper_daily_report(
    *,
    report_date: date,
    trades: Sequence[PaperTrade],
    generated_at: datetime | None = None,
) -> ForwardPaperDailyReport:
    """Build one deterministic UTC-day report from auditable paper trades."""

    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise ValueError("forward-paper report generation time must be timezone-aware")

    relevant = tuple(
        sorted(
            (
                trade
                for trade in trades
                if trade.created_at.astimezone(timezone.utc).date() <= report_date
            ),
            key=lambda trade: (trade.created_at, trade.trade_id),
        )
    )
    created_today = tuple(
        trade
        for trade in relevant
        if trade.created_at.astimezone(timezone.utc).date() == report_date
    )
    closed_today = tuple(
        trade
        for trade in relevant
        if trade.exit_time is not None
        and trade.exit_time.astimezone(timezone.utc).date() == report_date
    )
    open_trades = tuple(trade for trade in relevant if trade.state not in TERMINAL_STATES)
    lifecycle_events = [
        event
        for trade in relevant
        for event in trade.lifecycle_events
        if _event_date(event) == report_date
    ]
    event_counts = Counter(str(event["event_type"]) for event in lifecycle_events)
    state_counts = Counter(trade.state.value for trade in relevant)
    closed_r = [trade.realized_r_multiple for trade in closed_today]
    closed_pnl = [trade.net_pnl for trade in closed_today]
    wins = sum(value > 0.0 for value in closed_pnl)

    payload: dict[str, Any] = {
        "schema_version": FORWARD_PAPER_DAILY_REPORT_SCHEMA_VERSION,
        "report_date": report_date.isoformat(),
        "generated_at": generated.astimezone(timezone.utc).isoformat(),
        "counts": {
            "cumulative_trades": len(relevant),
            "created_today": len(created_today),
            "closed_today": len(closed_today),
            "open_trades": len(open_trades),
            "lifecycle_events_today": len(lifecycle_events),
        },
        "performance": {
            "realized_net_pnl_today": sum(closed_pnl),
            "realized_r_today": sum(closed_r),
            "average_r_today": sum(closed_r) / len(closed_r) if closed_r else 0.0,
            "win_rate_today": wins / len(closed_pnl) if closed_pnl else 0.0,
        },
        "by_state": dict(sorted(state_counts.items())),
        "lifecycle_event_counts": dict(sorted(event_counts.items())),
        "open_trade_ids": [trade.trade_id for trade in open_trades],
        "closed_trade_ids_today": [trade.trade_id for trade in closed_today],
        "warnings": [
            "This report is a paper-validation artifact, not evidence of live profitability.",
            "Production eligibility requires separate forward-edge and risk-policy review.",
        ],
    }
    report_hash = _hash_payload(payload)
    payload["report_sha256"] = report_hash
    return ForwardPaperDailyReport(payload=payload, report_sha256=report_hash)


def write_forward_paper_daily_report(
    report: ForwardPaperDailyReport,
    path: Path,
    *,
    force: bool = False,
) -> None:
    """Persist one report atomically without silent overwrite."""

    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite forward-paper daily report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report.payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_and_verify_forward_paper_daily_report(path: Path) -> ForwardPaperDailyReport:
    """Reload a persisted report and verify its deterministic payload hash."""

    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("forward-paper daily report must be a JSON object")
    payload = cast(dict[str, Any], dict(value))
    report_hash = payload.pop("report_sha256", None)
    if not isinstance(report_hash, str) or not report_hash:
        raise ValueError("forward-paper daily report hash is missing")
    if _hash_payload(payload) != report_hash:
        raise ValueError("forward-paper daily report hash does not match its payload")
    payload["report_sha256"] = report_hash
    return ForwardPaperDailyReport(payload=payload, report_sha256=report_hash)


def _event_date(event: dict[str, Any]) -> date | None:
    value = event.get("occurred_at")
    if not isinstance(value, str):
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("paper lifecycle event time must be timezone-aware")
    return parsed.astimezone(timezone.utc).date()


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
