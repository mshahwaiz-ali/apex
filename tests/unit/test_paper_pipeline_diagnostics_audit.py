from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apex.application.paper_pipeline import run_locked_paper_pipeline
from apex.paper_trading.intake import IntakeMarketType, IntakeSummary
from apex.paper_trading.scheduler import ScheduledPaperCycleResult


def test_pipeline_persists_scanner_and_strategy_diagnostics(tmp_path: Path) -> None:
    started_at = datetime.now(UTC) - timedelta(seconds=1)
    diagnostics = {
        "scan_analysis_count": 4,
        "scanner_failure_count": 1,
        "scanner_failures": {"ETH/USDT": "provider timeout"},
        "strategy_analysis": {
            "BTC/USDT": {
                "near_miss_state_counts": {"wait_for_retest": 1},
                "higher_timeframe_breakout": True,
            }
        },
    }

    result = run_locked_paper_pipeline(
        market_type=IntakeMarketType.FUTURES,
        data_dir=tmp_path,
        started_at=started_at,
        run_id="diagnostic-run",
        diagnostics=diagnostics,
        run_intake=lambda: IntakeSummary(
            market_type=IntakeMarketType.FUTURES,
            candidates_observed=0,
            accepted=0,
            rejected=0,
            duplicates_skipped=0,
            persistence_failures=0,
            reason_counts={},
            created_trade_ids=(),
            results=(),
        ),
        run_cycle=lambda: ScheduledPaperCycleResult(
            market_type="futures",
            started_at=started_at,
            completed_at=started_at,
            runtime={},  # type: ignore[arg-type]
            lock_path="cycle.lock",
            log_path="cycle.jsonl",
        ),
    )

    log_path = tmp_path / "paper_trading/scheduler/logs/pipeline-futures.jsonl"
    payload = json.loads(log_path.read_text(encoding="utf-8"))

    assert dict(result.diagnostics or {}) == diagnostics
    assert payload["diagnostics"]["scan_analysis_count"] == 4
    assert payload["diagnostics"]["scanner_failure_count"] == 1
    assert payload["diagnostics"]["scanner_failures"] == {
        "ETH/USDT": "provider timeout"
    }
    assert payload["diagnostics"]["strategy_analysis"]["BTC/USDT"] == {
        "higher_timeframe_breakout": True,
        "near_miss_state_counts": {"wait_for_retest": 1},
    }
