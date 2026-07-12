# Phase 9 Codex Handoff

`docs/plan.md` remains the authoritative roadmap. This document records the implemented Phase 9 paper-trading foundation.

## Phase 9 Scope

Implemented:

* paper-trading package boundary: `apex.paper_trading`
* immutable paper-trade lifecycle contracts
* local JSON paper-trade store
* setup recording from approved risk setups
* entry simulation
* stop, target, invalidation, timeout, and expiry lifecycle updates
* conservative intrabar handling
* live paper-performance metrics
* CLI commands under `apex paper`

Out of scope:

* real order placement
* exchange accounts
* persistent database migrations
* dashboards
* scheduled daemon process

## CLI Commands

```text
apex paper record BTC/USDT
apex paper update
apex paper report
apex paper report --output json
```

Default storage path:

```text
data/paper_trading/trades.json
```

## Files Implemented

* `src/apex/paper_trading/__init__.py`
* `src/apex/paper_trading/contracts.py`
* `src/apex/paper_trading/engine.py`
* `src/apex/paper_trading/store.py`
* `src/apex/cli.py`
* `tests/unit/paper_trading/test_engine_and_store.py`
* `tests/integration/test_cli_market_data.py`

## Public APIs

* `PaperTradeState`
* `PaperTradeConfig`
* `PaperTrade`
* `PaperPerformance`
* `PaperTradeStore`
* `create_paper_trade`
* `update_paper_trade`
* `summarize_paper_trades`

## Key Invariants

* Paper trading never imports execution or order-placement modules.
* Paper trades are immutable lifecycle records.
* Terminal paper trades require an exit time.
* Waiting setups can expire before entry if target is reached, stop is violated, or timeout is reached.
* Entered setups can close through stop, target, or holding-period expiry.
* Ambiguous stop-and-target candles resolve conservatively by default.
* JSON storage round-trips full audit payloads including the original analysis payload.

## Validation

Focused local validation:

```text
.venv/bin/python -m pytest tests/unit/paper_trading/test_engine_and_store.py tests/integration/test_cli_market_data.py
11 passed

.venv/bin/python -m ruff check src/apex/paper_trading src/apex/cli.py tests/unit/paper_trading/test_engine_and_store.py tests/integration/test_cli_market_data.py
All checks passed!

.venv/bin/python -m mypy src
Success: no issues found in 83 source files
```
