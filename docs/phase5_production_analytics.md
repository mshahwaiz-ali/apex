# Phase 5 production analytics

The futures paper pipeline now persists a shared Phase 5 scoring and selection analytics payload alongside the existing Phase 4 diagnostics.

The payload is generated once by `build_futures_pipeline_diagnostics()` and is written to:

- futures intake JSONL audit records;
- futures pipeline JSONL audit records;
- `paper scheduled-futures-pipeline --output json`.

## Run-level summary

`diagnostics.phase5_summary` contains two production funnels.

```json
{
  "analysis_funnel": {
    "observed": 0,
    "with_candidates": 0,
    "selected": 0,
    "no_trade": 0
  },
  "candidate_funnel": {
    "scored": 0,
    "ranked": 0,
    "accepted": 0,
    "rejected": 0,
    "downgraded": 0
  }
}
```

It also exposes deterministic maps for:

- candidate outcome counts;
- outcomes by strategy;
- outcomes by scanner category;
- candidate counts by strategy;
- selected counts by strategy and direction when an explicit selected candidate identity is available;
- no-trade reason counts;
- score-band counts;
- average final score by strategy.

The score bands follow the current project interpretation:

- `85_100_exceptional`;
- `75_84_strong`;
- `65_74_valid_aggressive`;
- `55_64_weak_experimental`;
- `below_55_rejected`.

## Per-analysis payload

`diagnostics.phase5_analyses` preserves normal and gainer paths independently using canonical keys such as:

```text
BTC/USDT:NORMAL_MARKET
BTC/USDT:GAINER
```

Each record contains candidate, ranked and rejected counts, selected/no-trade state, outcome totals and the existing ranked-candidate details.

## Missing data behavior

The analytics layer does not infer a selected strategy from accepted candidates because final selection may include consensus bonuses. Strategy and direction selection counts are emitted only when an explicit selected candidate identifier is available. Missing or partial diagnostics produce empty or zero aggregates rather than fabricated values.
