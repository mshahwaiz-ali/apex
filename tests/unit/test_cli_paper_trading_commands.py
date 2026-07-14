from __future__ import annotations

import typer
from typer.testing import CliRunner

from apex.application import normalize_market_symbol
from apex.cli_commands import paper_trading


def _paper_app() -> typer.Typer:
    app = typer.Typer()
    paper_trading.register_paper_trading_commands(app)
    return app


def test_paper_commands_are_registered() -> None:
    result = CliRunner().invoke(_paper_app(), ["--help"])

    assert result.exit_code == 0, result.output
    assert "record" in result.output
    assert "update" in result.output


def test_compact_symbols_use_canonical_normalization() -> None:
    assert normalize_market_symbol("1000PEPEUSDT") == "1000PEPE/USDT"
    assert normalize_market_symbol("BTCUSDT") == "BTC/USDT"
