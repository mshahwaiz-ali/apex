"""Tests for trader-facing system and market-data presentation."""

from __future__ import annotations

from apex.presentation.system import (
    render_candles,
    render_config,
    render_smoke,
    render_ticker,
    render_version,
)


def test_ticker_is_readable_and_includes_spread() -> None:
    rendered = render_ticker(
        {
            "symbol": "BTCUSDT",
            "last_price": 100.0,
            "bid_price": 99.9,
            "ask_price": 100.1,
            "quote_volume_24h": 1_500_000.0,
            "captured_at": "2026-07-16T12:00:00+00:00",
            "source": "binance",
        }
    )

    assert "Market Ticker — BTCUSDT" in rendered
    assert "Spread percentage" in rendered
    assert "0.20%" in rendered
    assert "24h quote volume" in rendered
    assert '"last_price"' not in rendered


def test_ticker_preserves_precision_for_tiny_spread_percentage() -> None:
    rendered = render_ticker(
        {
            "symbol": "BTCUSDT",
            "last_price": 64_560.01,
            "bid_price": 64_560.00,
            "ask_price": 64_560.01,
            "quote_volume_24h": 1_500_000.0,
            "captured_at": "2026-07-16T12:00:00+00:00",
            "source": "binance",
        }
    )

    assert "Spread percentage" in rendered
    assert "0.000015%" in rendered
    assert "0.0%" not in rendered


def test_candles_include_detailed_rows() -> None:
    candles = [
        {
            "symbol": "ETHUSDT",
            "timeframe": "5m",
            "open_time": "2026-07-16T11:50:00+00:00",
            "close_time": "2026-07-16T11:55:00+00:00",
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 500.0,
            "is_closed": True,
            "source": "binance",
        },
        {
            "symbol": "ETHUSDT",
            "timeframe": "5m",
            "open_time": "2026-07-16T11:55:00+00:00",
            "close_time": "2026-07-16T12:00:00+00:00",
            "open": 101.0,
            "high": 104.0,
            "low": 100.0,
            "close": 103.0,
            "volume": 750.0,
            "is_closed": True,
            "source": "binance",
        },
    ]

    text = render_candles(candles)

    assert "Market Candles — ETHUSDT" in text
    assert "Latest Candle" in text
    assert "Period change" in text
    assert "| O " in text


def test_config_includes_resolved_settings() -> None:
    payload = {
        "environment": "development",
        "analysis_timeframes": ["5m", "15m", "1h"],
        "data_dir": "data",
        "cache_enabled": True,
    }

    text = render_config(payload)

    assert "Status" in text
    assert "Valid" in text
    assert "Provider" in text
    assert "Binance" in text
    assert "5m, 15m, 1h" in text
    assert "Resolved Settings" in text


def test_smoke_and_version_are_professional() -> None:
    smoke = render_smoke({"status": "ok", "version": "0.1.0", "environment": "development"})
    version = render_version("0.1.0")

    assert "Apex System Check" in smoke
    assert "Application: Ready" in smoke
    assert "Apex Trading Agent" in version
    assert "Version: 0.1.0" in version
