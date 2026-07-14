# V1 — Historical Edge and Dataset Pipeline

## Status

The V1 historical-edge foundation, leakage-safe query orchestration, curated dataset manifests,
structured dataset validation, deterministic backtest-outcome conversion, and SQLite import audit
storage are present on `main`.

The complete local quality gate remains pending. No historical profitability, funded readiness, or
production-readiness claim is made by this implementation state.

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

### V1.4 curated dataset manifests

`CuratedDatasetManifest` records stable dataset identity and audit information independently from
file names and modification timestamps.

The manifest includes:

- dataset ID and market type;
- source type and source identifier;
- exchange/provider;
- symbols and timeframes;
- candle count;
- first and last timestamps;
- timezone and expected interval;
- canonical content hash;
- schema and creation timestamps;
- explicit partitions;
- optional notes;
- data-quality flags;
- duplicate, missing-interval, malformed-row, and out-of-order counts.

The content hash is generated from canonical candle records. Mapping key order and record order do
not change the resulting hash. Unstable filesystem metadata is not part of the identity.

### Structured candle validation

Raw candle records are validated before conversion to the strict `Candle` domain contract. Source
rows are never silently sorted, deduplicated, filled, or repaired.

Validation returns one of:

- `VALID`;
- `VALID_WITH_WARNINGS`;
- `INVALID`.

Structured validation issues cover:

- missing required fields;
- malformed or timezone-naive timestamps;
- non-finite values;
- impossible OHLC geometry;
- negative volume;
- duplicate symbol/timeframe timestamps;
- non-chronological source rows;
- unsupported or inconsistent intervals;
- explicit missing-interval warnings;
- expected count, symbol, timeframe, and timestamp mismatches;
- partitions outside the dataset range.

Missing intervals are warnings and remain visible in the manifest. Duplicate timestamps, malformed
OHLC, negative volume, invalid timestamps, and invalid partition ranges are errors.

### Backtest outcome conversion

`convert_backtest_trades()` converts terminal entered `SimulatedTrade` records into
`HistoricalOutcome` without fabricating unavailable evidence.

The adapter requires:

- actual `entry_time`;
- positive `executed_entry_price`;
- regime;
- MFE in R;
- MAE in R;
- finite fee-adjusted net PnL and realized R.

These fields are consumed from trade audit metadata until the backtest engine emits them directly.
A missing field produces an explicit rejection rather than a guessed default.

Accepted outcomes map:

- stable setup ID;
- dataset ID;
- market type;
- strategy and symbol;
- regime and score band;
- open and close timestamps;
- fee-preserving net return;
- realized R, MFE R, and MAE R;
- win/loss result.

`net_return` is defined as:

```text
fee-adjusted net_pnl / executed entry notional
```

Fees and slippage are not subtracted again during conversion.

### Split assignment and rejection policy

Split assignment uses the actual entry timestamp with half-open boundaries:

```text
partition.start_at <= entry_time < partition.end_at
```

A trade is rejected when:

- it never entered (`MISSED_ENTRY`);
- actual entry evidence is unavailable;
- regime, MFE, or MAE evidence is unavailable;
- entry falls outside all declared partitions;
- close occurs after the assigned partition ends;
- the fee-adjusted result is exactly zero while `HistoricalOutcome` remains win/loss-only;
- metrics are invalid or non-finite;
- the deterministic setup identity is duplicated within the import.

`TARGET`, `STOP`, and entered `EXPIRED` outcomes may be accepted when all required evidence exists.
Cross-partition outcomes are rejected to avoid using later-split candles for an earlier split result.

### Deterministic reporting and query orchestration

Historical-edge reports contain schema version, deterministic result hash, exact market/strategy/
split identity, optional segment dimensions, evidence quality, sample counts, metrics, dataset IDs,
and referenced dataset metadata.

Stored outcomes are queried with exact SQL filters and deterministic chronological ordering. Final
`TEST` access remains blocked unless `allow_final_test=True` is explicitly supplied.

Zero-sample queries remain valid `INSUFFICIENT` outputs and never create edge claims.

### SQLite persistence and import audit

The original historical-edge schema remains intact. V1.4 adds non-destructive schema-version `2`
objects:

```text
historical_dataset_manifests
historical_outcome_imports
```

Storage behavior includes:

- WAL journal mode;
- deterministic JSON payloads;
- stable manifest and import identities;
- idempotent upserts;
- atomic persistence of import audit plus accepted outcomes;
- no duplicate outcome rows by setup ID;
- manifest and import round-trip loading;
- accepted, rejected, duplicate, and rejection-reason audit counts.

Futures and spot remain explicitly separated by `market_type`.

## Important boundaries

Only completed chronological outcomes may enter historical-edge aggregation. Active, unresolved,
cancelled, and unentered records must not contribute.

An `INSUFFICIENT` result is valid evidence output. It must not be converted into a positive,
negative, funded, or production-readiness claim.

The `TEST` split remains reserved for one-time final out-of-sample evaluation. Dataset registration,
conversion, persistence, and query capability do not themselves authorize repeated final-test use.

V1.4 does not integrate historical evidence into funded eligibility. That work remains a later
increment after dataset and conversion validation.

## Important files

```text
src/apex/application/historical_edge.py
src/apex/application/historical_edge_io.py
src/apex/application/historical_edge_query.py
src/apex/application/historical_dataset_manifest.py
src/apex/application/historical_outcome_conversion.py
src/apex/application/historical_dataset_io.py

tests/unit/application/test_historical_edge.py
tests/unit/application/test_historical_edge_io.py
tests/unit/application/test_historical_edge_query.py
tests/unit/application/test_historical_dataset_manifest.py
tests/unit/application/test_historical_outcome_conversion.py
tests/unit/application/test_historical_dataset_io.py
```

## Validation commands

```bash
ruff format .
ruff check .
mypy src
pytest --import-mode=importlib tests/unit/application/test_historical_dataset_manifest.py
pytest --import-mode=importlib tests/unit/application/test_historical_outcome_conversion.py
pytest --import-mode=importlib tests/unit/application/test_historical_dataset_io.py
pytest --import-mode=importlib
```

Do not declare V1.4 validated until the complete local quality gate passes.

## Remaining V1 work

- update the backtest engine to emit actual entry timestamp, executed entry price, MFE R, and MAE R;
- propagate the replay-timeframe regime into chronological trade audit metadata;
- add engine-level regression coverage for entry and excursion evidence;
- add V1.5 CLI dataset registration/import/query/report commands;
- define V1.6 one-time final-test consumption and audit policy;
- integrate validated evidence into futures and spot eligibility only in V1.7 or the roadmap-defined
  equivalent;
- update application-level public exports after local gate validation.
