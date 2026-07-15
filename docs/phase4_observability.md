# Phase 4 production observability

The scheduled futures paper pipeline emits one shared Phase 4 diagnostic payload to:

- futures intake JSONL audit records;
- futures pipeline JSONL audit records;
- `paper scheduled-futures-pipeline --output json`;
- the concise scheduled-pipeline text summary.

The aggregation is built once by `build_futures_pipeline_diagnostics()` and preserves the existing `phase4_analyses` records keyed by both symbol and scanner category, for example:

```text
BTC/USDT:NORMAL_MARKET
BTC/USDT:GAINER
```

## Run-level payload

`diagnostics.phase4_summary` contains deterministic, alphabetically ordered maps for:

- `rejection_code_counts`;
- `rejection_counts_by_strategy`;
- `rejection_counts_by_scanner_category`;
- `rejection_counts_by_decision_regime`;
- `rejection_counts_by_near_miss_state`;
- `candidate_counts_by_strategy`.

It also contains:

```json
{
  "strategy_totals": {
    "evaluated": 0,
    "eligible": 0,
    "skipped": 0,
    "producing_candidates": 0,
    "producing_zero_candidates": 0
  },
  "higher_timeframe_breakout_fallback": {
    "detected": 0,
    "eligible_because_of_fallback": 0,
    "raw_candidate_produced": 0,
    "no_candidate_despite_fallback": 0
  }
}
```

Counts are derived only from enum-backed rejection codes and stable routing fields. Missing or partial routing diagnostics produce empty or zero aggregates rather than inferred data.

## Text output

The scheduled futures pipeline text line adds three compact fields:

```text
phase4_candidates=<count> | phase4_rejections=<count> | htf_fallback_eligible=<count>
```

Detailed per-symbol diagnostics remain available in JSON and audit logs, so the terminal summary stays compact.
