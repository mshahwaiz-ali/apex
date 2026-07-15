from __future__ import annotations

import json
from datetime import UTC, datetime

from apex.application.paper_intake import append_intake_log
from apex.paper_trading.intake import IntakeMarketType, IntakeSummary


def test_append_intake_log_includes_scanner_diagnostics(tmp_path) -> None:
    path = tmp_path / "paper_trading" / "scheduler" / "intake-futures.jsonl"
    started_at = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    summary = IntakeSummary(
        market_type=IntakeMarketType.FUTURES,
        candidates_observed=4,
        accepted=0,
        rejected=4,
        duplicates_skipped=0,
        persistence_failures=0,
        reason_counts={"NO_APPROVED_SETUP": 4},
        created_trade_ids=(),
        results=(),
    )

    append_intake_log(
        path,
        started_at=started_at,
        summary=summary,
        diagnostics={
            "scan_analysis_count": 4,
            "scanner_failure_count": 1,
            "scanner_failures": {"gainer:BAD/USDT": "provider failure"},
        },
    )

    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["candidates_observed"] == 4
    assert payload["diagnostics"]["scan_analysis_count"] == 4
    assert payload["diagnostics"]["scanner_failure_count"] == 1
    assert payload["diagnostics"]["scanner_failures"] == {
        "gainer:BAD/USDT": "provider failure"
    }
