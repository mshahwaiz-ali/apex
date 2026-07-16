"""Tests for independent funded-plan package reproduction."""

from __future__ import annotations

from datetime import date, datetime, timezone

from apex.funded import (
    DrawdownModel,
    FundedPlanReproductionStatus,
    ProviderPolicyBinding,
    build_funded_plan_evidence_package,
    verify_funded_plan_package_reproduction,
)


def _binding() -> ProviderPolicyBinding:
    return ProviderPolicyBinding(
        provider_id="APEX_TEST",
        provider_name="Apex Test Funding",
        challenge_phase="PHASE_1",
        preset_sha256="a" * 64,
        verification_date=date(2026, 7, 16),
        drawdown_model=DrawdownModel.STATIC,
        weekend_trading_allowed=False,
        overnight_holding_allowed=False,
        news_trading_allowed=False,
        compatible=True,
    )


def _sources() -> dict[str, object]:
    binding = _binding()
    return {
        "setup": {"symbol": "BTCUSDT", "score": 88},
        "account": {"equity": 10000},
        "account_policy": {"type": "FUNDED"},
        "account_state": {"daily_loss_pct": 0.0},
        "provider_binding": binding,
        "futures_config": {"margin_mode": "ISOLATED"},
        "strategy_approval_config": {"minimum_score": 75},
        "funded_plan": {
            "status": "APPROVED",
            "funded_eligibility": {
                "state": "ELIGIBLE_FOR_FUNDED_REVIEW",
                "reasons": [],
                "provider_name": binding.provider_name,
                "challenge_phase": binding.challenge_phase,
                "provider_preset_sha256": binding.preset_sha256,
                "execution_authorized": False,
            },
            "execution_authorized": False,
        },
    }


def _package():
    sources = _sources()
    return build_funded_plan_evidence_package(
        setup=sources["setup"],
        account=sources["account"],
        account_policy=sources["account_policy"],
        account_state=sources["account_state"],
        provider_binding=sources["provider_binding"],
        futures_config=sources["futures_config"],
        strategy_approval_config=sources["strategy_approval_config"],
        funded_plan=sources["funded_plan"],
        generated_at=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
    )


def _verify(sources: dict[str, object]):
    return verify_funded_plan_package_reproduction(
        _package(),
        setup=sources["setup"],
        account=sources["account"],
        account_policy=sources["account_policy"],
        account_state=sources["account_state"],
        provider_binding=sources["provider_binding"],
        futures_config=sources["futures_config"],
        strategy_approval_config=sources["strategy_approval_config"],
        regenerated_funded_plan=sources["funded_plan"],
    )


def test_identical_sources_reproduce_package() -> None:
    report = _verify(_sources())

    assert report.status is FundedPlanReproductionStatus.VERIFIED
    assert report.verified is True
    assert report.mismatch_names == ()
    assert len(report.checks) == 8
    assert all(check.matches for check in report.checks)
    assert report.execution_authorized is False


def test_setup_mismatch_is_identified() -> None:
    sources = _sources()
    sources["setup"] = {"symbol": "ETHUSDT", "score": 88}

    report = _verify(sources)

    assert report.status is FundedPlanReproductionStatus.MISMATCH
    assert report.verified is False
    assert report.mismatch_names == ("setup",)


def test_regenerated_plan_mismatch_is_identified() -> None:
    sources = _sources()
    funded_plan = dict(sources["funded_plan"])
    funded_plan["status"] = "REJECTED"
    sources["funded_plan"] = funded_plan

    report = _verify(sources)

    assert report.mismatch_names == ("funded_plan",)


def test_multiple_source_mismatches_are_reported_in_stable_order() -> None:
    sources = _sources()
    sources["account"] = {"equity": 9999}
    sources["futures_config"] = {"margin_mode": "CROSS"}

    report = _verify(sources)

    assert report.mismatch_names == ("account", "futures_config")


def test_reproduction_rejects_authorizing_regenerated_plan() -> None:
    sources = _sources()
    funded_plan = dict(sources["funded_plan"])
    funded_plan["execution_authorized"] = True
    sources["funded_plan"] = funded_plan

    try:
        _verify(sources)
    except ValueError as exc:
        assert "non-authorizing" in str(exc)
    else:
        raise AssertionError("authorizing regenerated plan was accepted")
