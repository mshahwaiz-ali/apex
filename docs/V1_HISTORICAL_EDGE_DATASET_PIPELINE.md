# V1 — Historical Edge and Dataset Pipeline

## Status

Implementation foundation and SQLite/report persistence are present on `main`.
The complete local quality gate remains pending.

## Implemented scope

### Historical evidence contracts

- explicit `FUTURES` and `SPOT` market segmentation;
- explicit chronological `TRAIN`, `VALIDATION`, and `TEST` partitions;
- deterministic dataset and result hashes;
- completed-outcome-only aggregation;
- setup-specific segmentation by strategy, symbol, regime, and score band;
- win rate, expectancy, average win/loss, profit factor, MFE, and MAE;
- explicit `INSUFFICIENT`, `PRELIMINARY`, and `ESTABLISHED` evidence states;
- clear insufficient-sample reasons;
- no final-test leakage into train or validation aggregation.

### Deterministic report serialization

Historical-edge reports contain:

- schema version;
- deterministic result hash;
- market type and strategy;
- exact dataset split;
- optional symbol, regime, and score-band segment;
- evidence quality and sample counts;
- setup-specific metrics;
- referenced dataset IDs;
- complete referenced dataset metadata and content hashes.

Reports are written atomically and refuse accidental overwrite unless explicitly forced.

### SQLite persistence

Schema version `1` stores:

- curated dataset metadata;
- completed chronological outcomes;
- aggregate historical-edge reports.

Storage behavior includes:

- WAL journal mode;
- idempotent upserts;
- deterministic JSON payloads;
- indexed market/strategy/split lookups;
- lightweight aggregate-report metadata listing;
- report loading by deterministic result hash.

Futures and spot rows remain explicitly separated by `market_type`.

## Important boundaries

V1 does not fabricate edge from incomplete or active trades.
Only completed chronological outcomes may enter aggregation.

An `INSUFFICIENT` result is valid evidence output. It must not be converted into a positive,
negative, funded, or production-readiness claim.

The `TEST` split is reserved for final out-of-sample evaluation. Training and validation reports
must be generated independently and must not consume final-test outcomes.

## Important files

```text
src/apex/application/historical_edge.py
src/apex/application/historical_edge_io.py
tests/unit/application/test_historical_edge.py
tests/unit/application/test_historical_edge_io.py
```

## Validation commands

```bash
ruff format .
ruff check .
mypy src
pytest --import-mode=importlib tests/unit/application/test_historical_edge.py
pytest --import-mode=importlib tests/unit/application/test_historical_edge_io.py
pytest --import-mode=importlib
```

Do not declare V1 validated until the complete local quality gate passes.

## Remaining V1 work

- connect curated candle/backtest datasets to `HistoricalOutcome` generation;
- add read/query APIs for stored datasets and completed outcomes;
- add an orchestration service that generates segmented reports from stored outcomes;
- add CLI commands for dataset registration, aggregation, report export, and inspection;
- define immutable final-test consumption rules at orchestration level;
- update application-level public exports after local gate validation;
- integrate validated historical evidence into futures and spot eligibility decisions.
