"""Verify scan and selected-symbol analysis share one canonical core."""

from __future__ import annotations

import ast
import inspect
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from apex.application import decision_analysis, selected_symbol
from apex.cli_commands import analysis as analysis_cli
from apex.cli_commands import scanner as scanner_cli
from apex.market_environment import DEFAULT_MARKET_ENVIRONMENT_CONFIG


def test_selected_symbol_delegates_to_canonical_analysis_core(monkeypatch: Any) -> None:
    calls: list[tuple[str, object, dict[str, object]]] = []
    expected = object()
    provider = object()

    def fake_analyze_symbol(
        symbol: str,
        received_provider: object,
        **kwargs: object,
    ) -> object:
        calls.append((symbol, received_provider, kwargs))
        return expected

    monkeypatch.setattr(selected_symbol, "analyze_symbol", fake_analyze_symbol)

    result = selected_symbol.analyze_selected_symbol(
        " btc/usdt ",
        provider,  # type: ignore[arg-type]
        timeframes=("1m", "15m"),
        candle_limit=240,
        methodology_gate_mode="enforce",
    )

    assert result is expected
    assert calls == [
        (
            "BTC/USDT",
            provider,
            {
                "timeframes": ("1m", "15m"),
                "timeframe_roles": None,
                "timeframe_max_staleness_seconds": None,
                "candle_limit": 240,
                "generated_at": None,
                "strategy_routing": None,
                "methodology_gate_mode": "enforce",
            },
        )
    ]


def test_scan_delegates_every_symbol_to_canonical_analysis_core(monkeypatch: Any) -> None:
    timestamp = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    calls: list[tuple[str, object, dict[str, object]]] = []
    provider = object()

    def fake_analyze_symbol(
        symbol: str,
        received_provider: object,
        **kwargs: object,
    ) -> object:
        calls.append((symbol, received_provider, kwargs))
        return SimpleNamespace(
            symbol=symbol,
            assessment=SimpleNamespace(setup=None),
            candidate_ranking=None,
        )

    monkeypatch.setattr(decision_analysis, "analyze_symbol", fake_analyze_symbol)

    result = decision_analysis.scan_symbols(
        ("ETHUSDT", "BTCUSDT"),
        provider,  # type: ignore[arg-type]
        timeframes=("1m", "15m"),
        candle_limit=240,
        generated_at=timestamp,
        methodology_gate_mode="enforce",
    )

    assert {item.symbol for item in result.analyses} == {"BTCUSDT", "ETHUSDT"}
    assert calls == [
        (
            "ETHUSDT",
            provider,
            {
                "timeframes": ("1m", "15m"),
                "timeframe_roles": None,
                "timeframe_max_staleness_seconds": None,
                "candle_limit": 240,
                "generated_at": timestamp,
                "strategy_routing": None,
                "market_environment_config": DEFAULT_MARKET_ENVIRONMENT_CONFIG,
                "methodology_gate_mode": "enforce",
            },
        ),
        (
            "BTCUSDT",
            provider,
            {
                "timeframes": ("1m", "15m"),
                "timeframe_roles": None,
                "timeframe_max_staleness_seconds": None,
                "candle_limit": 240,
                "generated_at": timestamp,
                "strategy_routing": None,
                "market_environment_config": DEFAULT_MARKET_ENVIRONMENT_CONFIG,
                "methodology_gate_mode": "enforce",
            },
        ),
    ]


def test_scan_and_analyze_cli_forward_the_same_candle_limit() -> None:
    scan_value = _call_keyword_value(
        scanner_cli.register_scanner_commands,
        call_name="scan_symbols",
        keyword="candle_limit",
    )
    analyze_value = _call_keyword_value(
        analysis_cli.register_analysis_commands,
        call_name="analyze_selected_symbol",
        keyword="candle_limit",
    )

    assert isinstance(scan_value, ast.Name)
    assert scan_value.id == "candle_limit"
    assert isinstance(analyze_value, ast.Name)
    assert analyze_value.id == "candle_limit"


def _call_keyword_value(
    function: Callable[..., object],
    *,
    call_name: str,
    keyword: str,
) -> ast.expr:
    tree = ast.parse(inspect.getsource(function))
    matches = [
        item
        for item in ast.walk(tree)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Name)
        and item.func.id == call_name
    ]
    assert len(matches) == 1
    values = [item.value for item in matches[0].keywords if item.arg == keyword]
    assert len(values) == 1
    return values[0]
