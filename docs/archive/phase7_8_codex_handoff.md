# Phase 7 and 8 Codex Handoff

`docs/plan.md` remains the authoritative roadmap. This document records the implemented Phase 7 CLI/scanner slice and Phase 8 backtesting foundation.

## Phase 7 Scope

Implemented:

* `apex analyze SYMBOL`
* `apex scan`
* text and JSON output
* optional JSON report export for analysis and scanner commands
* configured symbol loading from `config/symbols.yaml`
* per-symbol scanner failure isolation
* deterministic Phase 4 to Phase 6 orchestration through `apex.application.analysis`

The scanner currently runs symbols sequentially to preserve deterministic provider behavior. Concurrency/rate-limit tuning can be added later behind the same application boundary.

## Phase 8 Scope

Implemented:

* backtesting package boundary: `apex.backtesting`
* immutable replay contracts
* conversion from risk-approved setup to replay signal
* deterministic entry, stop, target, expiry, fee, and slippage simulation
* conservative intrabar ambiguity handling
* aggregate report metrics
* `apex backtest SYMBOL` for simulating the current approved setup against fetched candles

Not implemented yet:

* full historical rolling-window signal generation
* walk-forward train/validation/test splits
* partial target execution
* strategy optimization
* persisted backtest reports

## Files Implemented

* `src/apex/application/analysis.py`
* `src/apex/backtesting/__init__.py`
* `src/apex/backtesting/contracts.py`
* `src/apex/backtesting/engine.py`
* `src/apex/cli.py`
* `tests/unit/application/test_application_analysis.py`
* `tests/unit/backtesting/test_engine.py`
* `tests/integration/test_cli_market_data.py`

## Public APIs

Application:

* `analyze_symbol`
* `scan_symbols`
* `load_symbols`
* `serialize_symbol_analysis`
* `serialize_scan_result`
* `format_symbol_text`
* `format_scan_text`
* `write_json_report`

Backtesting:

* `BacktestConfig`
* `BacktestSignal`
* `SimulatedTrade`
* `BacktestReport`
* `BacktestOutcome`
* `signal_from_setup`
* `simulate_trade`
* `summarize_trades`

## Key Invariants

* The CLI does not make trade decisions itself.
* Application analysis uses the existing deterministic Phase 4, 5, and 6 stack.
* Scanner failures are isolated per symbol.
* Backtesting does not assume the profitable side of an ambiguous candle by default.
* Unfilled replay signals expire flat.
* Backtest signal prices must be directionally valid.
* Backtest metrics are deterministic from the provided simulated trades.

## Validation

Focused tests added for:

* symbol config validation
* scanner failure isolation
* scanner serialization
* CLI analyze/scan/backtest command wiring
* conservative intrabar replay behavior
* short replay behavior
* expiry behavior
* summary metrics by symbol and strategy

Run full local gate:

```text
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src
.venv/bin/python -m pytest --cov=apex --cov-report=term-missing
```
