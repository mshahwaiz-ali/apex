# V1 — Historical Edge and Dataset Pipeline

## Status

Implementation foundation, SQLite/report persistence, and leakage-safe query orchestration are
present on `main`. The complete local quality gate remains pending.

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

### Leakage-safe query orchestration

`HistoricalEdgeQueryRequest` defines one exact evidence segment using:

- market type;
- strategy;
- split;
- optional dataset ID;
- optional symbol;
- optional regime;
- optional score band;
- explicit evidence thresholds.

Stored outcomes are queried with exact SQL filters and returned in deterministic chronological
order. No fallback query broadens the requested segment.

`run_historical_edge_query()`:

1. loads only the requested completed outcomes;
2. aggregates only the requested split;
3. loads metadata for the exact referenced datasets;
4. fails closed when referenced dataset metadata is missing;
5. builds a deterministic self-contained report;
6. optionally persists the aggregate report by result hash.

Final `TEST` access is blocked by default. A caller must set `allow_final_test=True` explicitly.
This prevents normal training or validation workflows from consuming the held-out final partition
accidentally.

Zero-sample queries remain valid `INSUFFICIENT` evidence results and do not create edge claims.

## Important boundaries

V1 does not fabricate edge from incomplete or active trades. Only completed chronological outcomes
may enter aggregation.

An `INSUFFICIENT` result is valid evidence output. It must not be converted into a positive,
negative, funded, or production-readiness claim.

The `TEST` split is reserved for final out-of-sample evaluation. Training and validation reports
must be generated independently and must not consume final-test outcomes.

Explicit final-test access prevents accidental leakage but does not itself establish organizational
approval or production readiness. That policy remains outside the aggregation engine.

## Important files

```text
src/apex/application/historical_edge.py
src/apex/application/historical_edge_io.py
src/apex/application/historical_edge_query.py
tests/unit/application/test_historical_edge.py
tests/unit/application/test_historical_edge_io.py
tests/unit/application/test_historical_edge_query.py
```

## Validation commands

```bash
ruff format .
ruff check .
mypy src
pytest --import-mode=importlib tests/unit/application/test_historical_edge.py
pytest --import-mode=importlib tests/unit/application/test_historical_edge_io.py
pytest --import-mode=importlib tests/unit/application/test_historical_edge_query.py
pytest --import-mode=importlib
```

Do not declare V1 validated until the complete local quality gate passes.

## Remaining V1 work

- connect curated candle/backtest datasets to `HistoricalOutcome` generation;
- add CLI commands for dataset registration, aggregation, report export, and inspection;
- update application-level public exports after local gate validation;
- integrate validated historical evidence into futures and spot eligibility decisions;
- define one-time final-test consumption/audit policy above the query engine;
- add dataset curation manifests and source-file hash generation.
