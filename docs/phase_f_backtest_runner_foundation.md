# Phase F Backtest Runner Foundation

This note records the first Phase F hardening slice.

## Added

- `HistoricalBacktestRunner.run(request) -> BacktestStudy`
- `BacktestRequest`
- `BacktestStudy`
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

## Current Scope

- This runner consumes deterministic precomputed signals.
- Full in-run pipeline generation at every historical decision timestamp is
  still pending for the deeper Phase F work.
- Portfolio exposure simulation, partial target fills, and stop/target
  ambiguity are still handled by the existing single-signal simulation model
  until the full chronological pipeline runner is implemented.
