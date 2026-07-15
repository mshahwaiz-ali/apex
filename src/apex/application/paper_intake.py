"""Application orchestration for automatic paper opportunity intake."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from apex.application.analysis import ScanResult, SymbolAnalysis
from apex.application.spot_live_scanner import SpotLiveScanResult
from apex.paper_trading.intake import (
    IntakeCandidate,
    IntakeMarketType,
    IntakeResult,
    IntakeSummary,
    build_futures_intake_candidate,
    build_spot_intake_candidate,
    intake_summary_payload,
    persist_intake_candidates,
)
from apex.paper_trading.scheduler import paper_cycle_lock
from apex.paper_trading.store import PaperTradeStore

FuturesPlanBuilder = Callable[[SymbolAnalysis], dict[str, Any] | None]


def intake_futures_scan(
    *,
    scan: ScanResult,
    store: PaperTradeStore,
    plan_builder: FuturesPlanBuilder,
    source_command: str = "paper intake-futures",
) -> IntakeSummary:
    """Admit only approved, actionable futures plans from one scanner result."""

    candidates: list[IntakeCandidate | IntakeResult] = []
    for analysis in scan.analyses:
        plan = plan_builder(analysis) if analysis.assessment.setup is not None else None
        management = plan.get("management_plan") if isinstance(plan, dict) else None
        account_policy = None
        if isinstance(plan, dict):
            account_policy = {
                "policy": plan.get("account_policy"),
                "decision": plan.get("account_policy_decision"),
                "risk_mode_config": plan.get("risk_mode_config"),
            }
        candidates.append(
            build_futures_intake_candidate(
                analysis,
                futures_plan=plan,
                management_plan=management if isinstance(management, dict) else None,
                account_policy_snapshot=account_policy,
                source_command=source_command,
                source_mode=scan.scanner_mode.value,
            )
        )
    return persist_intake_candidates(
        store,
        tuple(candidates),
        market_type=IntakeMarketType.FUTURES,
    )


def intake_spot_scan(
    *,
    scan: SpotLiveScanResult,
    store: PaperTradeStore,
    analysis_timestamp: datetime,
    source_command: str = "paper intake-spot",
) -> IntakeSummary:
    """Admit approved long-only cash-spot plans from one live scanner result."""

    candidates = tuple(
        build_spot_intake_candidate(
            symbol=item.symbol,
            result=item.result,
            analysis_timestamp=analysis_timestamp,
            source_command=source_command,
            source_mode=scan.mode.value,
            scanner_context={
                "eligibility": {
                    "eligible": item.eligibility.eligible,
                    "reason_codes": [reason.value for reason in item.eligibility.reasons],
                },
                "metadata": item.metadata.model_dump(mode="json"),
            },
        )
        for item in scan.ranked
    )
    return persist_intake_candidates(
        store,
        candidates,
        market_type=IntakeMarketType.SPOT,
    )


def run_locked_paper_intake(
    *,
    market_type: IntakeMarketType,
    data_dir: Path,
    started_at: datetime,
    run: Callable[[], IntakeSummary],
    stale_after: timedelta = timedelta(minutes=30),
) -> IntakeSummary:
    """Run one intake invocation under the existing scheduler lock protocol."""

    lock_path = data_dir / "paper_trading" / "locks" / f"intake-{market_type.value}.lock"
    with paper_cycle_lock(lock_path, acquired_at=started_at, stale_after=stale_after):
        summary = run()
        _append_intake_log(
            data_dir / "paper_trading" / "scheduler" / f"intake-{market_type.value}.jsonl",
            started_at=started_at,
            summary=summary,
        )
        return summary


def _append_intake_log(
    path: Path,
    *,
    started_at: datetime,
    summary: IntakeSummary,
) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "started_at": started_at.astimezone(UTC).isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        **intake_summary_payload(summary),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")


def candidate_count(items: Iterable[object]) -> int:
    """Return a stable count for scheduler diagnostics and tests."""

    return sum(1 for _ in items)
