from __future__ import annotations

import pytest

from apex.presentation.scan_groups import (
    ScanGroup,
    classify_scan_result,
    flatten_existing_scan_groups,
    group_scan_results,
)


def _result(status: str | None) -> dict[str, object]:
    setup: dict[str, object] | None = None
    if status is not None:
        setup = {
            "entry_status": status,
            "strategy": "momentum_breakout",
            "direction": "long",
        }
    return {"symbol": f"{status or 'NONE'}/USDT", "setup": setup}


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("READY_NOW", ScanGroup.READY),
        ("AGGRESSIVE_NOW", ScanGroup.AGGRESSIVE),
        ("PULLBACK_PREFERRED", ScanGroup.CONDITIONAL),
        ("WAIT_FOR_RETEST", ScanGroup.CONDITIONAL),
        ("WATCH_NEAR_ENTRY", ScanGroup.DEVELOPING),
        ("LATE_OR_CHASING", ScanGroup.UNAVAILABLE),
        ("INVALIDATED", ScanGroup.UNAVAILABLE),
        (None, ScanGroup.NO_SETUP),
    ],
)
def test_scan_result_classification(
    status: str | None,
    expected: ScanGroup,
) -> None:
    assert classify_scan_result(_result(status)) is expected


def test_grouped_counts_keep_setup_and_no_setup_separate() -> None:
    grouped = group_scan_results(
        (
            _result("READY_NOW"),
            _result("PULLBACK_PREFERRED"),
            _result("WATCH_NEAR_ENTRY"),
            _result(None),
        )
    )

    assert len(grouped.ready) == 1
    assert len(grouped.conditional) == 1
    assert len(grouped.developing) == 1
    assert len(grouped.no_setup) == 1


def test_flatten_existing_groups_removes_duplicate_result_identity() -> None:
    item = _result("WATCH_NEAR_ENTRY")
    payload = {
        "developing_setups": [item],
        "no_trade_results": [item],
    }

    assert flatten_existing_scan_groups(payload) == (item,)
