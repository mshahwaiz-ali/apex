from __future__ import annotations

from apex.presentation.cli_information_architecture import (
    ScanInformationSection,
    data_quality_warning,
    partition_scan_results,
)
from apex.presentation.operator_output import render_analysis, render_scan


def _setup(
    *,
    status: str,
    strategy: str = "breakout_continuation",
    direction: str = "long",
    warnings: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "direction": direction,
        "strategy": strategy,
        "entry_status": status,
        "confidence_score": 82.0,
        "execution_allowed_now": status == "READY_NOW",
        "entry": {
            "current_price": 100.0,
            "lower": 99.5,
            "upper": 100.5,
            "preferred": 100.0,
            "maximum_chase_price": 101.0,
            "distance_from_current": 0.0,
        },
        "stop_loss": {"price": 97.0},
        "take_profits": (
            {"price": 103.0, "risk_reward": 1.0},
            {"price": 106.0, "risk_reward": 2.0},
            {"price": 109.0, "risk_reward": 3.0},
        ),
        "quality_dimensions": {
            "setup_quality": 84.0,
            "execution_quality": 79.0,
            "continuation_quality": 76.0,
            "overall_trade_quality": 81.0,
        },
        "initial_risk_reward": 1.0,
        "runner_risk_reward": 3.0,
        "alignment_classification": "aligned",
        "warnings": warnings,
        "evidence": ("breakout accepted", "volume expanded"),
    }


def test_scan_information_partition_matches_required_sections() -> None:
    results = (
        {"symbol": "AAAUSDT", "setup": _setup(status="READY_NOW")},
        {"symbol": "BBBUSDT", "setup": _setup(status="WAIT_FOR_RETEST")},
        {
            "symbol": "CCCUSDT",
            "setup": _setup(
                status="RECLAIM_REQUIRED",
                warnings=("Wait for close confirmation",),
            ),
        },
        {
            "symbol": "DDDUSDT",
            "developing_setup": _setup(
                status="DEVELOPING",
                strategy="range_reversal",
            ),
        },
        {"symbol": "EEEUSDT", "setup": _setup(status="INVALIDATED")},
    )

    groups = partition_scan_results(results)

    assert tuple(item["symbol"] for item in groups.actionable_cmp) == ("AAAUSDT",)
    assert tuple(item["symbol"] for item in groups.nearby_limit) == ("BBBUSDT",)
    assert tuple(item["symbol"] for item in groups.micro_confirmation) == ("CCCUSDT",)
    assert tuple(item["symbol"] for item in groups.follow_up_reversal) == ("DDDUSDT",)
    assert tuple(item["symbol"] for item in groups.weak_invalid) == ("EEEUSDT",)


def test_scan_output_preserves_essential_compact_fields() -> None:
    payload = {
        "total_analysis_count": 5,
        "displayed_analysis_count": 1,
        "selected_setup_count": 1,
        "results": (
            {
                "symbol": "BTCUSDT",
                "setup": _setup(status="READY_NOW"),
                "methodology_completeness": {
                    "unavailable_fields": ("depth_imbalance",),
                },
            },
        ),
    }

    output = render_scan(payload)

    assert "Actionable at CMP" in output
    assert "Current price" in output
    assert "Entry zone" in output
    assert "Ideal entry" in output
    assert "Maximum chase" in output
    assert "TP1 RR" in output
    assert "Setup / execution" in output
    assert "Data quality" in output


def test_analysis_output_preserves_full_trade_geometry_and_diagnostics() -> None:
    setup = _setup(status="READY_NOW")
    payload = {
        "symbol": "BTCUSDT",
        "setup": setup,
        "nearby_alternative": _setup(status="WAIT_FOR_RETEST"),
        "opposite_follow_up": _setup(
            status="DEVELOPING",
            strategy="range_reversal",
            direction="short",
        ),
        "reasons": ("breakout accepted",),
        "opportunity_collision": {"resolution": "coexist"},
        "runner_decision": {"decision": "tighten_and_hold"},
        "methodology_completeness": {
            "unavailable_fields": ("liquidation_impulse",),
        },
    }

    output = render_analysis(payload, explain=True)

    assert "Trade plan" in output
    assert "Current price" in output
    assert "Preferred entry" in output
    assert "Do not chase above" in output
    assert "Target 1" in output
    assert "Opportunity map" in output
    assert "Current opportunity" in output
    assert "Nearby alternative" in output
    assert "Opposite follow-up" in output
    assert "Diagnostics" in output
    assert "Collision: Coexist" in output
    assert "Runner: Tighten And Hold" in output
    assert "Data quality" in output


def test_invalidated_setup_is_not_rendered_as_executable() -> None:
    setup = _setup(status="INVALIDATED")
    setup["execution_allowed_now"] = True

    output = render_analysis({"symbol": "BTCUSDT", "setup": setup})

    assert "ENTER LONG" not in output
    assert "WAIT FOR ACTIVATION" in output


def test_uncalibrated_historical_reliability_remains_visible() -> None:
    payload = {
        "symbol": "BTCUSDT",
        "setup": _setup(status="READY_NOW"),
        "historical_edge": {
            "available": False,
            "reason": "historical edge unavailable: artifact missing",
        },
    }

    output = render_analysis(payload)

    assert "Historical edge" in output
    assert "Not validated yet" in output


def test_data_quality_warning_does_not_invent_absent_warning() -> None:
    assert data_quality_warning({}) is None
    assert (
        data_quality_warning(
            {
                "market_evidence": {
                    "disposition": "degraded",
                }
            }
        )
        == "Optional market evidence is incomplete"
    )


def test_section_enum_values_are_stable() -> None:
    assert ScanInformationSection.ACTIONABLE_CMP.value == "actionable_cmp"
    assert ScanInformationSection.WEAK_INVALID.value == "weak_invalid"
