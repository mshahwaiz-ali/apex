from __future__ import annotations

import json
from dataclasses import asdict, fields
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apex.application.paper_lifecycle_analytics import PaperLifecycleAnalytics
from apex.application.paper_lifecycle_health import PaperLifecycleHealthStatus
from apex.application.paper_lifecycle_health_io import load_latest_paper_lifecycle_health
from apex.paper_trading.intake import IntakeMarketType


def _analytics(**overrides: object) -> PaperLifecycleAnalytics:
    values: dict[str, object] = {
        "intake_candidates_observed": 25,
        "intake_accepted": 22,
        "intake_rejected": 3,
        "duplicates_skipped": 0,
        "persistence_failures": 0,
        "intake_reason_counts": {},
        "loaded_trades": 20,
        "eligible_trades": 20,
        "advanced_trades": 20,
        "unchanged_trades": 0,
        "missing_candle_trades": 0,
        "requested_symbols": 20,
        "successful_symbols": 20,
        "provider_failure_count": 0,
        "provider_failures_by_symbol": {},
        "state_counts": {"target_hit": 12, "stopped": 8},
        "entry_state_counts": {},
        "waiting_for_entry": 0,
        "entered_trades": 20,
        "unfilled_terminal_trades": 0,
        "partial_target_fills": 6,
        "full_target_completions": 12,
        "stop_loss_exits": 8,
        "expired_trades": 0,
        "invalidations": 0,
        "cancelled_trades": 0,
        "transition_counts": {},
        "transition_reason_counts": {},
        "realized_net_pnl": 10.0,
        "average_realized_r_multiple": 0.5,
        "risk_multiple_distribution": {},
        "leverage_distribution": {},
        "holding_time_distribution": {},
        "average_margin": 10.0,
        "average_wallet_exposure_pct": 8.0,
        "total_fees": 1.0,
        "total_slippage": 0.5,
        "trades": (),
    }
    values.update(overrides)
    assert values.keys() == {field.name for field in fields(PaperLifecycleAnalytics)}
    return PaperLifecycleAnalytics(**values)  # type: ignore[arg-type]


def _record(
    run_id: str,
    market: str,
    *,
    outcome: str = "success",
    analytics: PaperLifecycleAnalytics | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 3,
        "run_id": run_id,
        "outcome": outcome,
        "market_type": market,
        "completed_at": "2026-07-16T12:00:00+00:00",
        "lifecycle_analytics": {} if analytics is None else asdict(analytics),
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def test_loader_selects_latest_successful_market_record(tmp_path: Path) -> None:
    path = tmp_path / "pipeline-futures.jsonl"
    _write_jsonl(
        path,
        [
            _record("old", "futures", analytics=_analytics(realized_net_pnl=1.0)),
            _record("spot", "spot", analytics=_analytics(realized_net_pnl=99.0)),
            _record("failed", "futures", outcome="failure", analytics=_analytics()),
            _record("latest", "futures", analytics=_analytics(realized_net_pnl=12.0)),
        ],
    )

    audit = load_latest_paper_lifecycle_health(
        path,
        market_type=IntakeMarketType.FUTURES,
    )

    assert audit.run_id == "latest"
    assert audit.market_type is IntakeMarketType.FUTURES
    assert audit.completed_at == datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    assert audit.analytics.realized_net_pnl == 12.0
    assert audit.health.status is PaperLifecycleHealthStatus.HEALTHY


def test_loader_skips_success_records_without_analytics(tmp_path: Path) -> None:
    path = tmp_path / "pipeline-futures.jsonl"
    _write_jsonl(
        path,
        [
            _record("valid", "futures", analytics=_analytics()),
            _record("empty", "futures"),
        ],
    )

    audit = load_latest_paper_lifecycle_health(
        path,
        market_type=IntakeMarketType.FUTURES,
    )

    assert audit.run_id == "valid"


def test_loader_rejects_missing_or_malformed_audit(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jsonl"
    with pytest.raises(FileNotFoundError, match="does not exist"):
        load_latest_paper_lifecycle_health(
            missing,
            market_type=IntakeMarketType.FUTURES,
        )

    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_latest_paper_lifecycle_health(
            malformed,
            market_type=IntakeMarketType.FUTURES,
        )


def test_loader_requires_matching_analytics_record(tmp_path: Path) -> None:
    path = tmp_path / "pipeline-futures.jsonl"
    _write_jsonl(path, [_record("spot", "spot", analytics=_analytics())])

    with pytest.raises(ValueError, match="no successful analytics-bearing futures"):
        load_latest_paper_lifecycle_health(
            path,
            market_type=IntakeMarketType.FUTURES,
        )


def test_loader_rejects_incomplete_analytics_contract(tmp_path: Path) -> None:
    path = tmp_path / "pipeline-futures.jsonl"
    payload = asdict(_analytics())
    payload.pop("state_counts")
    record = _record("broken", "futures", analytics=_analytics())
    record["lifecycle_analytics"] = payload
    _write_jsonl(path, [record])

    with pytest.raises(ValueError, match="missing fields: state_counts"):
        load_latest_paper_lifecycle_health(
            path,
            market_type=IntakeMarketType.FUTURES,
        )
