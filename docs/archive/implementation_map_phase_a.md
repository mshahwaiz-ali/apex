# Apex Phase A Implementation Map

Source of truth: `docs/plan_2.md`.

This map records the Phase A audit baseline and the immediate correctness work. It is not a profitability, production-readiness, or execution-readiness claim.

## Implemented Module Surface

Core package areas currently present under `src/apex/`:

* `application`: bootstrap, symbol analysis orchestration, scanner serialization, market-data service construction.
* `backtesting`: deterministic single-signal replay contracts and summary metrics.
* `config`: YAML and environment settings loader.
* `data`: provider protocols, Binance public provider, HTTP helper, file candle cache, candle validation.
* `domain`: candle and ticker domain models.
* `execution`: local testnet simulation safety boundary, audit log, duplicate-key tracking, kill switch.
* `features`: moving averages, trend, momentum, volatility, volume, price-location features, registry, numerical validation.
* `intelligence`: disabled-by-default deterministic metadata surface.
* `liquidity`: zones, sweeps, traps, registry, analysis result contracts.
* `optimization`: report comparison/evaluation contracts and result persistence.
* `paper_trading`: local paper trade lifecycle, JSON persistence, performance summaries.
* `risk`: controlled risk assessment, position sizing, leverage/liquidation modeling, exposure checks.
* `scoring`: candidate scoring, consensus, conflict penalties, ranking and selection.
* `strategies`: trend pullback, breakout continuation, momentum continuation, liquidity reversal, range reversal, entry contracts.
* `structure`: swings, levels, breaks, ranges, trend, regime, registry, analysis contracts.

## CLI Map

Functional local commands:

* `apex version`
* `apex validate-config`
* `apex smoke`
* `apex fetch`
* `apex ticker`
* `apex analyze`
* `apex scan`
* `apex backtest`
* `apex paper record`
* `apex paper update`
* `apex paper report`
* `apex optimize evaluate`
* `apex optimize compare`
* `apex intelligence summary`
* `apex execute preview`
* `apex execute status`
* `apex execute kill-switch enable`

Simulated local command:

* `apex execute testnet` records a local testnet simulation event only. It does not submit an order to an exchange.

## Current Quality Gates

Baseline command set:

```text
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
.venv/bin/pytest --cov=apex --cov-report=term-missing
git diff --check
```

Initial Phase A baseline before terminology fixes:

* Ruff passed.
* Format check passed.
* Mypy passed for 92 source files.
* Pytest passed with 363 tests.
* Coverage was 84%.
* `git diff --check` passed.

Final Phase A verification after terminology fixes:

* Ruff passed.
* Format check passed.
* Mypy passed for 92 source files.
* Pytest passed with 365 tests.
* Coverage remained 84%.
* `git diff --check` passed.

The project virtualenv is the correct validation environment. The system `python3` is missing project dependencies and should not be used for gate results.

## Coverage Gaps

Known lower-coverage areas from the Phase A baseline include:

* CLI command branches.
* Application scanner serialization and failure branches.
* Intelligence contracts and optional metadata paths.
* Optimization rejection/report branches.
* Some structure, liquidity, risk, and execution contract validation branches.

Do not add an arbitrary coverage threshold until the baseline is intentionally raised.

## Known Misleading Behavior Corrected

The execution module previously exposed a state named `testnet_submitted` even though the implementation only wrote a local audit event. Phase A corrected this boundary:

* The public state is now `local_testnet_simulated`.
* The explicit implementation entrypoint is `simulate_testnet_order`.
* `submit_testnet_order` remains as a compatibility wrapper for existing imports.
* CLI text now reports `EXECUTE_LOCAL_TESTNET_SIMULATION`.
* `apex execute status` now reports `mode=local_testnet_simulation_only`.

Real exchange testnet submission remains unimplemented and must not be represented as available.
