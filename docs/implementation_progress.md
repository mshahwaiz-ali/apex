# Apex Futures Implementation Progress

## Baseline Repair

Status: completed

Baseline before implementation:

- Working tree was clean.
- Focused futures/application tests passed: `19 passed`.
- Full pytest failed in `tests/integration/test_cli_market_data.py::test_analyze_command_emits_text_result`.
- Ruff, Ruff format check, and strict mypy failed on lifecycle/futures formatting, export ordering, and a lifecycle `Self` return annotation.

Repairs started:

- Modular `apex analyze` now handles no-trade/fake analysis objects without dereferencing `result.assessment` unconditionally.
- Lifecycle snapshot transition returns are annotated concretely for strict mypy.
- Existing long lifecycle/futures lines and domain export ordering were cleaned up.

Validation after repair:

- `.venv/bin/python -m mypy src` passed.
- `.venv/bin/python -m pytest` passed with `475 passed`.

## Phase A - Direction-Aware Entry Classification

Status: completed

Implemented:

- Added canonical `EntryClassificationInput`, `EntryClassificationResult`, and `classify_entry_state`.
- Classification is direction-aware for long and short setups and uses deterministic precedence: invalidated, missed, ready now, retest, reclaim, approaching, watch, no trade.
- Futures-plan mapping no longer uses the old `inside_zone ? READY_NOW : APPROACHING_ENTRY` shortcut.
- Analysis and scan serialization expose `entry_state` and `entry_classification`.

Tests:

- Added table-driven boundary and precedence tests for long and short states.
- Added futures-plan integration tests for missed long entries and short retests.

## Phase B - Futures Sizing, Costs, Leverage, and Liquidation

Status: completed

Implemented:

- Added validated execution-cost assumptions to `config/futures.yaml`.
- Position plans are now sized from wallet loss allowance, structural stop distance, modeled fees, and modeled slippage.
- Automatic leverage selects the closest valid risk-mode leverage while enforcing wallet exposure and liquidation buffer.
- Manual leverage is preserved exactly when safe and rejected with explicit profile-bound or safety reasons when unsafe.
- Position output includes quantity, notional, margin, wallet exposure, modeled loss components, estimated liquidation, stop-to-liquidation buffer, leverage-selection reason, limiting constraint, and approximation warnings.

Tests:

- Updated futures-plan tests for fee/slippage-inclusive account sizing.
- Existing futures contract/config tests continue to pass.

## Phases C-F - Scanner Categories, Gainer State, Precision/Routing Metadata

Status: partially completed

Implemented:

- Added `MarketCategory`, `ScannerMode`, `GainerState`, `GainerStateInput`, `GainerStateResult`, and `classify_gainer_state`.
- `scan_symbols` supports `normal`, `gainers`, and `all` modes. Default remains `normal` for compatibility.
- `all` mode runs normal-market and gainer paths independently and preserves `scanner_type`.
- Gainer classification records evidence and missing optional data instead of fabricating unavailable inputs.
- Analysis serialization includes scanner type, gainer-state evidence, and strategy-routing metadata.
- Text output now includes the canonical entry state for approved setups.
- Added `PrecisionEntryPlan` and `PrecisionEntryScore` with component scores separate from generic setup confidence.
- Analysis and futures-plan outputs now include `precision_entry`.
- Analysis precision-entry output now includes deterministic 5m/3m/1m trigger state, reclaim/retest/fast-failure trigger levels, trigger timeframes, and trigger evidence when low-timeframe context is available.
- Added deterministic strategy-routing metadata with separate enabled/disabled strategy lists for normal-market and gainer scanner paths.
- Added validated `strategy_routing` configuration in `config/default.yaml` and threaded it through analysis, scan, selected-symbol analysis, CLI commands, and chronological backtests.
- Added validated `gainer_state_thresholds` configuration in `config/default.yaml` and threaded it through scan, selected-symbol analysis, CLI commands, and chronological backtests.
- Strategy routing now filters Phase 4 candidates before scoring, so scanner route configuration is enforced instead of being metadata-only.
- Routing payloads now include decision regime, routed eligible strategies, skipped strategy reasons, selected-strategy route eligibility, scanner-route rejections, and gainer-state routing rejections.
- Gainer scanner routes now reject `momentum_gainer_continuation` when the gainer state is distribution, breakdown, first exhaustion, failed breakdown bounce, terminal extension, or chaotic.
- Precision-entry scoring now uses ticker bid/ask spread when the active provider supplies ticker data, with deterministic penalties and evidence for acceptable/elevated/wide spreads.
- Added provider-independent `OrderBookSnapshot`, `OrderBookLevel`, and `ExchangeFilterSnapshot` contracts plus optional provider fetch plumbing.
- Binance Spot now implements order-book depth and exchange-filter fetches using public `/api/v3/depth` and `/api/v3/exchangeInfo` endpoints.
- Cached and resampled provider decorators delegate order-book and exchange-filter snapshots without caching or resampling them.
- Analysis data-quality serialization now exposes order-book spread, order-book depth imbalance, exchange tick size, exchange step size, and exchange minimum notional when a provider supplies them.
- Precision-entry scoring now uses order-book depth imbalance for liquidity quality and trap penalty, and reports exchange-filter availability separately from unavailable data.
- Added provider-independent liquidation-cluster contracts and optional provider fetch plumbing.
- Analysis data-quality serialization now exposes nearest long/short liquidation-cluster distances when a provider supplies them.
- Precision-entry scoring now increases trap risk for close adverse liquidation clusters and records nearby favorable liquidation clusters as target/magnet evidence.

Remaining:

- Liquidation-cluster confidence depends on optional provider snapshot availability.
- Order-book and exact exchange-filter confidence depend on optional provider snapshot availability; Binance Spot now supplies these fields.
- Spread confidence depends on provider ticker bid/ask availability.
- Strategy routing is now configuration-driven and regime-aware; more advanced symbol/session-specific route conditions remain future work.

Tests:

- Added gainer-state classifier tests, including the rule that high extension alone does not force a breakdown/short.
- Added configurable gainer-threshold tests.
- Added scan `all` mode serialization tests.
- Added precision-entry scoring, spread-penalty, and routing serialization tests.
- Added strategy-routing tests for scanner-route enforcement, unfavorable gainer-state rejection, and routing rejection explanations.
- Added provider-independent order-book/exchange-filter contract tests and precision-entry microstructure scoring tests.
- Added Binance order-book/exchange-filter adapter tests and cache/resampling passthrough tests.
- Added provider-independent liquidation-cluster contract tests and precision-entry cluster trap/magnet scoring tests.

## Phases G-L - Lifecycle, Storage, Backtesting, Calibration, Paper Trading, Testnet

Status: partially completed

Current state:

- Existing lifecycle, backtesting, paper trading, optimization, intelligence, and testnet-only execution foundations remain intact.
- Added `TradeLifecycleEvent`, `TradeLifecycleEventType`, and `replay_lifecycle_events` so lifecycle event streams can reconstruct validated snapshots deterministically.
- Lifecycle replay now preserves partial-target labels, active stop moves, runner activation, trailing-stop updates, expiry, invalidation, and terminal-state guards.
- Added schema-versioned `analysis_id` records with stable content hashes for analysis and scan payloads.
- `apex analyze --record ...` and `apex scan --record ...` can append JSONL records without replacing JSON report output.
- `apex analyze --record-db ...` and `apex scan --record-db ...` can upsert reproducible analysis/scan records into a local SQLite database.
- JSON reports now embed `record_metadata` for reproducibility.
- Paper trades now store optional canonical futures-plan snapshots and replayable lifecycle event records.
- `paper_lifecycle_snapshot()` replays paper lifecycle events through the canonical futures lifecycle validator.
- `apex paper replay-report ...` can replay stored paper lifecycle events into a JSON audit report with per-trade replay failures isolated.
- Paper-trade updates now support `partially_closed` state, target-ladder fills, replayable partial-target events, cumulative realized PnL, and backward-compatible store round-trips for target ladders and partial progress.
- Backtest trades and aggregate reports now support reproducibility metadata.
- Backtest signals now preserve full target ladders and partial-close percentages from approved setups.
- Deterministic trade simulation now realizes partial target fills, carries remaining quantity to later targets, stops, or expiry, and records `partial_target_count` plus `closed_percentage` metadata.
- Chronological pipeline trades preserve production decision metadata such as configuration ID, scanner type, entry state, and precision-entry score when an approved setup is simulated.
- `apex chronological-backtest --record-db ...` can upsert complete reproducible report payloads into a SQLite index keyed by stable run identity.
- Added provider-independent chronological backtest campaigns that run multiple deterministic variants through the production pipeline, rank variants by net profit/expectancy/drawdown, emit stable campaign IDs, and preserve complete per-variant report payloads.
- `apex chronological-backtest-campaign ...` can run default or explicit `id:timeframe:candles:interval:cooldown` variants from a local dataset or provider history.
- Chronological campaigns now support comma-separated curated multi-symbol inputs, fan out symbol-by-variant runs through the production pipeline, and rank results across symbols without merging candle timelines.
- Backtest campaign reports can be written to JSON and upserted into a local SQLite campaign index.
- Optimization report loading now accepts campaign JSON directly and evaluates the selected best variant aggregated across symbols, avoiding double-counting all variants in one campaign.
- Added walk-forward calibration evaluation contracts and `apex optimize calibrate`, comparing train and validation summaries while keeping the final test set isolated from candidate selection.
- Tightened the execution foundation around explicit local testnet-simulation environment contracts, deterministic client order IDs, deterministic idempotency keys, schema-versioned audit records, and explicit `live_fallback=false` audit/status output.
- Execution intents now preserve approved setup target ladders and partial-close percentages through preview/testnet simulation, deterministic idempotency keys, and schema-versioned audit records.
- Added a deterministic fake testnet adapter that reuses the canonical local simulation safety gates and records adapter identity in execution audit events.
- Added provider-independent execution reconciliation contracts and `apex execute reconcile`, comparing local audit events with deterministic adapter snapshots and reporting matched, missing, mismatched, and locally rejected events.
- Added `apex execute readiness`, which reports local simulation readiness separately from exchange readiness and lists explicit blockers for real exchange/testnet execution.
- Non-testnet execution configuration is rejected instead of being silently downgraded.
- This batch did not add real exchange-specific testnet connectivity.

External blockers and limits:

- No live top-gainer, funding, open-interest, order-book, liquidation, or exchange bracket feeds were available locally.
- No exchange/testnet credentials were used.
- Provider-independent contracts and deterministic fixtures were added where this batch touched scanner/gainer behavior.
- Provider-independent lifecycle replay contracts were added without requiring exchange connectivity.
- Provider-independent analysis record persistence now supports JSONL append logs and SQLite upsert storage. Parquet storage remains future work unless the repo gains a clean dependency path for it.

## Current Validation

Latest focused gate after execution readiness reporting:

- `.venv/bin/python -m pytest tests/unit/execution/test_execution_engine.py tests/integration/test_cli_market_data.py::test_execute_readiness_writes_report tests/integration/test_cli_market_data.py::test_execute_reconcile_writes_report` passed with `19 passed`.
- `.venv/bin/python -m mypy src/apex/execution src/apex/cli.py` passed.
- `.venv/bin/python -m ruff check .` passed.
- `.venv/bin/python -m ruff format --check .` passed.
- `.venv/bin/python -m mypy src` passed.
- `.venv/bin/python -m pytest` passed with `602 passed`.

Previous full gate after execution reconciliation:

- `.venv/bin/python -m pytest tests/unit/execution/test_execution_engine.py tests/integration/test_cli_market_data.py::test_execute_reconcile_writes_report` passed with `16 passed`.
- `.venv/bin/python -m mypy src/apex/execution src/apex/cli.py` passed.
- `.venv/bin/python -m ruff check .` passed.
- `.venv/bin/python -m ruff format --check .` passed.
- `.venv/bin/python -m mypy src` passed.
- `.venv/bin/python -m pytest` passed with `599 passed`.

Previous full gate after campaign-aware optimization:

- `.venv/bin/python -m pytest tests/unit/optimization/test_optimization_engine.py tests/integration/test_cli_market_data.py::test_optimize_evaluate_command_accepts_campaign_report tests/integration/test_cli_market_data.py::test_optimize_evaluate_command_writes_report tests/integration/test_cli_market_data.py::test_optimize_compare_command_emits_json` passed with `13 passed`.
- `.venv/bin/python -m mypy src/apex/optimization src/apex/cli.py` passed.
- `.venv/bin/python -m ruff check .` passed.
- `.venv/bin/python -m ruff format --check .` passed.
- `.venv/bin/python -m mypy src` passed.
- `.venv/bin/python -m pytest` passed with `595 passed`.

Previous full gate after multi-symbol chronological campaigns:

- `.venv/bin/python -m pytest tests/unit/application/test_backtest_campaign.py tests/integration/test_cli_market_data.py::test_chronological_campaign_command_runs_application_layer tests/integration/test_cli_market_data.py::test_chronological_campaign_command_supports_multi_symbol_dataset` passed with `8 passed`.
- `.venv/bin/python -m mypy src/apex/application/backtest_campaign.py src/apex/cli_commands/backtesting.py` passed.
- `.venv/bin/python -m ruff check .` passed.
- `.venv/bin/python -m ruff format --check .` passed.
- `.venv/bin/python -m mypy src` passed.
- `.venv/bin/python -m pytest` passed with `592 passed`.

Previous full gate after chronological backtest campaigns:

- `.venv/bin/python -m pytest tests/unit/application/test_backtest_campaign.py tests/unit/test_reproducible_baseline_io.py tests/integration/test_cli_market_data.py::test_analysis_and_scan_help_expose_record_option tests/integration/test_cli_market_data.py::test_chronological_campaign_command_runs_application_layer` passed with `14 passed`.
- `.venv/bin/python -m mypy src/apex/application/backtest_campaign.py src/apex/application/backtest_report_io.py src/apex/cli_commands/backtesting.py` passed.
- `.venv/bin/python -m ruff check .` passed.
- `.venv/bin/python -m ruff format --check .` passed.
- `.venv/bin/python -m mypy src` passed.
- `.venv/bin/python -m pytest` passed with `589 passed`.

Previous full gate after execution target-ladder simulation:

- `.venv/bin/python -m pytest tests/unit/execution/test_execution_engine.py tests/integration/test_cli_market_data.py::test_execute_status_reports_local_testnet_simulation_only tests/integration/test_cli_market_data.py::test_execute_testnet_reports_local_simulation` passed with `14 passed`.
- `.venv/bin/python -m ruff check .` passed.
- `.venv/bin/python -m ruff format --check .` passed.
- `.venv/bin/python -m mypy src` passed.
- `.venv/bin/python -m pytest` passed with `583 passed`.

Previous full gate after partial-target paper-trading lifecycle:

- `.venv/bin/python -m pytest tests/unit/paper_trading/test_engine_and_store.py tests/unit/test_cli_paper_trading_commands.py tests/integration/test_cli_market_data.py::test_paper_report_command_emits_metrics tests/integration/test_cli_market_data.py::test_paper_replay_report_command_writes_report` passed with `17 passed`.
- `.venv/bin/python -m ruff check .` passed.
- `.venv/bin/python -m ruff format --check .` passed.
- `.venv/bin/python -m mypy src` passed.
- `.venv/bin/python -m pytest` passed with `579 passed`.

Previous full gate after partial-target backtesting simulation:

- `.venv/bin/python -m ruff check .` passed.
- `.venv/bin/python -m ruff format --check .` passed.
- `.venv/bin/python -m mypy src` passed.
- `.venv/bin/python -m pytest` passed with `576 passed`.
- `git diff --check` passed.
