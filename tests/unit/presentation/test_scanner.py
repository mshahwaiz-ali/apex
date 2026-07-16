from __future__ import annotations

from apex.presentation.scanner import render_futures_scan


def _no_trade(symbol: str, *, preferred: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "decision": "NO_TRADE",
        "reasons": ["No approved precision-entry geometry is available"],
        "decision_reason_code": "NO_CANDIDATE_GENERATED",
        "market_environment": {
            "higher_timeframe_bias": "STRONGLY