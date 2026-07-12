# Phase 10-12 Codex Handoff

`docs/plan.md` remains the authoritative roadmap. This document records the roadmap-completion pass for optimization, optional intelligence, and testnet-only execution.

## Phase 10 — Optimization

Implemented:

* `apex.optimization` package
* immutable optimization run, split, parameter, summary, and result contracts
* baseline-vs-candidate comparison
* rejection of win-rate-only changes that reduce expectancy
* report persistence under `data/optimization/`
* CLI:
  * `apex optimize evaluate --input <report.json>`
  * `apex optimize compare --baseline <file> --candidate <file>`

Production config files are not edited automatically. Accepted candidates emit a recommended patch in the optimization report.

## Phase 11 — Advanced Intelligence

Implemented:

* `apex.intelligence` package
* funding-rate, open-interest, correlation, and market-risk contracts
* deterministic close-return correlation
* metadata-only market risk summaries
* disabled-by-default config flags
* optional provider protocols for derivatives data
* CLI:
  * `apex intelligence summary`

Intelligence output is metadata/warnings only. It does not approve, reject, rank, size, or execute trades.

## Phase 12 — Testnet-Only Execution

Implemented:

* `apex.execution` package
* execution intent/order/result/config contracts
* testnet-only submit safety engine
* explicit confirmation requirement
* duplicate-order key protection
* max notional guard
* daily-loss circuit breaker input
* local kill switch
* audit log under `data/execution/audit.jsonl`
* CLI:
  * `apex execute preview BTC/USDT`
  * `apex execute testnet BTC/USDT --confirm`
  * `apex execute kill-switch enable`
  * `apex execute status`

Execution is disabled by default. No real-money execution adapter or credential support is implemented.

## Validation Coverage

Added tests for:

* optimization acceptance/rejection rules
* optimization JSON report round-trip
* optimizer CLI commands
* intelligence disabled-by-default behavior
* deterministic correlation and metadata summaries
* execution disabled-by-default behavior
* testnet audit logging
* duplicate key and kill-switch rejection
* execution CLI status and kill-switch commands
* architecture boundaries for optimization, intelligence, and execution

Run full local gate:

```text
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src
.venv/bin/python -m pytest --cov=apex --cov-report=term-missing
git diff --check
```
