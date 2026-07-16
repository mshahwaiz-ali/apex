# N4.6 — Deterministic Multi-Timeframe Historical Dataset Campaigns

## Implemented

N4.6 extends the historical futures dataset campaign system from one timeframe per
symbol to a frozen deterministic symbol × timeframe acquisition matrix.

The campaign-plan schema is now version 2. New manifests explicitly freeze:

- the normalized symbol set;
- the canonical ordered timeframe set;
- provider and candle count;
- chronological split ratios;
- acquisition order;
- parent, train, validation, and final-test dataset IDs;
- parent, child, and split-manifest artifact paths.

Schema-version-1 campaign plans remain loadable and executable. Their singular
`timeframe` value is converted in memory to a one-element timeframe tuple, and their
symbol set is derived from the frozen jobs. Existing version-1 files are not rewritten.
All new writes use schema version 2.

Supported campaign timeframes are centrally validated and ordered as:

```text
1m, 3m, 5m, 15m, 30m, 1h, 4h
```

Planning uses normalized-symbol order first and canonical timeframe order second.
For two symbols and seven timeframes, the plan therefore contains fourteen jobs.
Repeated CLI `--timeframe` options are preserved rather than silently collapsing to
the final option.

A provider-independent matrix verifier rejects duplicate, missing, extra, or reordered
symbol/timeframe pairs. The same verifier is applied to frozen plans and completed
execution job sets. N4.5 execution remains responsible for acquisition, fail-fast
behavior, overwrite preflight, cleanup, persistence, split verification, and execution
manifest handling.

The installed CLI reports campaign symbol count, canonical timeframes, planned jobs,
completed jobs, failed jobs, status, and manifest path.

## Tests added or updated

Focused coverage includes:

- repeated CLI `--timeframe` options;
- canonical timeframe ordering;
- deterministic symbol/timeframe matrix ordering;
- exact matrix job counts;
- stable IDs across input ordering;
- duplicate, malformed, and unsupported timeframe rejection;
- schema-version-1 loading without file mutation;
- schema-version-2 JSON round trips;
- missing and duplicate matrix-pair rejection;
- N4.5 single-timeframe planner compatibility;
- exact frozen multi-timeframe provider-call order;
- multi-timeframe fake-provider CLI execution;
- provider mismatch and overwrite failure behavior.

## Explicit boundaries

Acquisition remains candle-count based. Date-range acquisition is not implemented.
N4.6 does not perform feature generation, historical signal generation, strategy replay,
chronological backtesting, historical-edge aggregation, calibration, optimization,
paper trading, testnet execution, or live execution.

N4.6 prepares complete frozen multi-timeframe input datasets for a later historical
signal-generation stage. It makes no profitability, trading-readiness, or execution-
readiness claim.

## Validation status

The repository's push-triggered GitHub quality workflow is responsible for Ruff format,
Ruff lint, strict mypy, and pytest validation. This implementation record does not claim
those checks passed until their actual output is inspected.
