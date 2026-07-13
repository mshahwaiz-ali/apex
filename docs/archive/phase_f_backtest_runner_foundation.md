# Phase F Backtest Runner Foundation

This note records the first Phase F hardening slice.

## Added

- `HistoricalBacktestRunner.run(request) -> BacktestStudy`
- `run_chronological_pipeline_backtest(request) -> ChronologicalBacktestResult`
- `BacktestRequest`
- `BacktestStudy`
- `ChronologicalBacktestRequest`
- `ChronologicalBacktestResult`
- Reproducibility hashes:
  - `dataset_hash`
  - `config_hash`
  - `code_hash`
- Explicit `MISSED_ENTRY` outcome for signals whose entry is never touched.

## Chronology And No Lookahead

- Study signals must be sorted chronologically.
- Each signal is replayed only against closed candles for the same symbol whose
  `open_time` is greater than or equal to the signal `generated_at`.
- Signals without future candles are skipped and counted separately.
- The full-pipeline runner builds an in-memory historical provider at each
  decision timestamp and only exposes candle prefixes whose `close_time` is at
  or before that timestamp.

## Current Scope

- `HistoricalBacktestRunner` consumes deterministic precomputed signals.
- `run_chronological_pipeline_backtest` runs the existing analysis, scoring, and
  risk stack at each historical decision timestamp.
- Portfolio exposure simulation, partial target fills, and stop/target
  ambiguity are still handled by the existing single-signal simulation model
  until the portfolio-level replay model is expanded.
