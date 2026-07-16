from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

from apex.application.paper_lifecycle_analytics import PaperLifecycleAnalytics
from apex.application.paper_lifecycle_health import PaperLifecycleHealthPolicy
from apex.application.paper_lifecycle_health_io import (
    build_paper_lifecycle_health_artifact,
    load_latest_paper_lifecycle_health,
    write_paper_lifecycle_health_artifact,
)
from apex.application.paper_lifecycle_health_verification import (
    PaperLifecycleHealthSourceStatus,
    paper_lifecycle_health_source_verification_payload,
    verify_paper_lifecycle_health_artifact_source,
)
from apex.paper_trading.intake import IntakeMarketType


def _analytics(**overrides: object) -> PaperLifecycleAnalytics:
    values: dict[str, object] = {
        "intake_candidates_observed": 20,
        "intake_accepted": 20,
        "intake_rejected": 0,
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


def _record(*, analytics: PaperLifecycleAnalytics | None = None) -> dict[str, object]:
    return {
        "schema_version": 3,
        "run_id": "run-1",
        "outcome": "success",
        "market_type": "futures",
        "completed_at": "2026-07-16T12:00:00+00:00",
        "lifecycle_analytics": asdict(_analytics() if analytics is None else analytics),
    }


def _write_artifact(tmp_path: Path) -> tuple[Path, Path]:
    source_log = tmp_path / "pipeline-futures.jsonl"
    source_log.write_text(json.dumps(_record(), sort_keys=True) + "\n", encoding="utf-8")
    policy = PaperLifecycleHealthPolicy()
    audit = load_latest_paper_lifecycle_health(
        source_log,
        market_type=IntakeMarketType.FUTURES,
        policy=policy,
    )
    artifact = build_paper_lifecycle_health_artifact(audit, policy=policy)
    artifact_path = tmp_path / "health.json"
    write_paper_lifecycle_health_artifact(artifact, artifact_path)
    return artifact_path, source_log


def test_source_verification_accepts_exact_evidence(tmp_path: Path) -> None:
    artifact_path, source_log = _write_artifact(tmp_path)

    verification = verify_paper_lifecycle_health_artifact_source(
        artifact_path,
        source_log,
    )
    payload = paper_lifecycle_health_source_verification_payload(verification)

    assert verification.status is PaperLifecycleHealthSourceStatus.VERIFIED
    assert verification.source_record_matches is True
    assert verification.source_log_matches is True
    assert verification.analytics_matches is True
    assert verification.identity_matches is True
    assert verification.execution_authorized is False
    assert verification.reasons == ()
    assert payload["status"] == "verified"
    assert payload["reasons"] == []


def test_source_verification_reports_append_only_log_change(tmp_path: Path) -> None:
    artifact_path, source_log = _write_artifact(tmp_path)
    source_log.write_text(
        source_log.read_text(encoding="utf-8")
        + json.dumps({"outcome": "failure", "run_id": "later"}, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    verification = verify_paper_lifecycle_health_artifact_source(
        artifact_path,
        source_log,
    )

    assert verification.status is PaperLifecycleHealthSourceStatus.SOURCE_LOG_CHANGED
    assert verification.source_record_matches is True
    assert verification.analytics_matches is True
    assert verification.identity_matches is True
    assert verification.source_log_matches is False
    assert verification.reasons == ("source_log_hash_mismatch",)


def test_source_verification_rejects_changed_source_record(tmp_path: Path) -> None:
    artifact_path, source_log = _write_artifact(tmp_path)
    source_log.write_text(
        json.dumps(_record(analytics=_analytics(realized_net_pnl=11.0)), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    verification = verify_paper_lifecycle_health_artifact_source(
        artifact_path,
        source_log,
    )

    assert verification.status is PaperLifecycleHealthSourceStatus.SOURCE_RECORD_INVALID
    assert verification.source_record_matches is False
    assert verification.analytics_matches is False
    assert verification.source_log_matches is False
    assert verification.reasons == (
        "source_record_hash_mismatch",
        "analytics_hash_mismatch",
        "source_log_hash_mismatch",
    )


def test_source_verification_rejects_wrong_log_name(tmp_path: Path) -> None:
    artifact_path, source_log = _write_artifact(tmp_path)
    renamed_log = tmp_path / "renamed.jsonl"
    renamed_log.write_bytes(source_log.read_bytes())

    verification = verify_paper_lifecycle_health_artifact_source(
        artifact_path,
        renamed_log,
    )

    assert verification.status is PaperLifecycleHealthSourceStatus.SOURCE_LOG_CHANGED
    assert verification.log_name_matches is False
    assert verification.source_record_matches is True
    assert verification.source_log_matches is True
    assert verification.reasons == ("source_log_name_mismatch",)


def test_source_verification_rejects_missing_declared_line(tmp_path: Path) -> None:
    artifact_path, source_log = _write_artifact(tmp_path)
    source_log.write_text("\n", encoding="utf-8")

    verification = verify_paper_lifecycle_health_artifact_source(
        artifact_path,
        source_log,
    )

    assert verification.status is PaperLifecycleHealthSourceStatus.SOURCE_RECORD_INVALID
    assert verification.observed_source_record_sha256 is None
    assert verification.observed_analytics_sha256 is None
    assert verification.reasons == (
        "source_line_empty",
        "source_record_hash_mismatch",
        "analytics_hash_mismatch",
        "source_identity_mismatch",
        "source_log_hash_mismatch",
    )


def test_source_verification_rejects_malformed_declared_line(tmp_path: Path) -> None:
    artifact_path, source_log = _write_artifact(tmp_path)
    source_log.write_text("not-json\n", encoding="utf-8")

    verification = verify_paper_lifecycle_health_artifact_source(
        artifact_path,
        source_log,
    )

    assert verification.status is PaperLifecycleHealthSourceStatus.SOURCE_RECORD_INVALID
    assert verification.reasons == (
        "source_line_invalid_json",
        "source_record_hash_mismatch",
        "analytics_hash_mismatch",
        "source_identity_mismatch",
        "source_log_hash_mismatch",
    )
