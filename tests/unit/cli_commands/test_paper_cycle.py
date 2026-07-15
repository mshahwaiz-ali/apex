from __future__ import annotations

from datetime import datetime, timezone

import pytest
import typer

from apex.cli_commands.paper_cycle import _parse_report_date, paper_runtime_payload
from apex.paper_trading import PaperOperationCycleResult, PaperRuntimeResult


def _runtime_result() -> PaperRuntimeResult:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    cycle = PaperOperationCycleResult(
        market_type="futures",
        started_at=now,
        completed_at=now,
        loaded_trade_count=2,
        eligible_trade_count=1,
        advanced_trade_count=1,
        unchanged_trade_count=0,
        missing_candle_trade_ids=(),
        trade_ids=("trade-1",),
    )
    return PaperRuntimeResult(
        cycle=cycle,
        requested_symbols=("BTCUSDT",),
        successful_symbols=(),
        provider_failures=(("BTCUSDT", "provider failure"),),
    )


def test_paper_runtime_payload_is_json_ready() -> None:
    payload = paper_runtime_payload(_runtime_result())

    assert payload["fully_collected"] is False
    assert payload["requested_symbols"] == ["BTCUSDT"]
    assert payload["provider_failures"] == [
        {"symbol": "BTCUSDT", "reason": "provider failure"}
    ]
    assert payload["cycle"]["market_type"] == "futures"
    assert payload["cycle"]["started_at"] == "2026-07-15T12:00:00+00:00"


def test_parse_report_date_accepts_iso_date_and_rejects_invalid_value() -> None:
    assert _parse_report_date("2026-07-15").isoformat() == "2026-07-15"
    assert _parse_report_date(None) is None

    with pytest.raises(typer.BadParameter, match="YYYY-MM-DD"):
        _parse_report_date("15-07-2026")
