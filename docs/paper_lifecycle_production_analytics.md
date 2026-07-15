# Paper lifecycle production analytics

Apex now has a typed analytics boundary for the post-approval paper-trading path.

## Scope

The subsystem consumes existing structured contracts only:

- `IntakeSummary` for intake funnel and duplicate suppression;
- `PaperRuntimeResult` for provider collection and runtime failures;
- `PaperOperationCycleResult` for loaded, eligible, advanced, unchanged, and missing-candle counts;
- `PaperTrade` for state, fills, lifecycle events, realized PnL, risk multiples, and holding duration;
- structured futures-plan fields for leverage, margin, wallet exposure, liquidation, fees, and slippage when present.

Missing financial fields remain `null`. The analytics layer does not fabricate values and does not derive lifecycle outcomes from notes.

## Run-level payload

`PaperLifecycleAnalytics` includes:

- intake candidates observed, accepted, rejected, duplicate-skipped, and persistence-failed;
- intake reason counts;
- loaded, eligible, advanced, unchanged, and missing-candle trades;
- requested and successfully collected symbols;
- provider failures and failures by symbol;
- state and entry-state distributions;
- waiting, entered, and unfilled-terminal totals;
- partial target fills and full target completions;
- stop, expiry, invalidation, and cancellation totals;
- lifecycle transition and transition-reason counts;
- realized net PnL and average realized risk multiple;
- risk-multiple, leverage, and holding-time distributions;
- average margin and wallet exposure;
- total fees and slippage when structured values exist;
- deterministic per-trade records.

## Stable bands

Risk-multiple bands:

```text
below_minus_1r
minus_1r_to_0r
0r_to_1r
1r_to_2r
above_2r
```

Leverage bands:

```text
1_5x
5_10x
10_20x
above_20x
```

Holding-time bands:

```text
not_entered
0_5_candles
6_12_candles
13_24_candles
above_24_candles
```

## Pipeline audit integration

`run_locked_paper_pipeline()` accepts an optional post-cycle analytics builder. The callback runs after lifecycle advancement and before the successful JSONL audit is written. Its result is persisted under:

```json
{
  "schema_version": 3,
  "lifecycle_analytics": {}
}
```

Failures in the analytics callback are recorded with:

```text
failed_stage=analytics
```

Legacy callers that do not provide the callback remain valid and emit an empty `lifecycle_analytics` mapping.

## Scheduled pipeline integration

Both scheduled commands now build lifecycle analytics from the canonical post-cycle store:

```text
paper scheduled-futures-pipeline
paper scheduled-spot-pipeline
```

The snapshot is filtered by market type before aggregation. Spot trades cannot affect futures analytics, and futures trades cannot affect spot analytics. Historical records without an explicit `market_type` retain the established futures default for backward compatibility.

The complete analytics payload is included in:

- successful paper pipeline JSONL audit records;
- scheduled command JSON output;
- the in-memory `PaperPipelineResult` contract.

Concise text output additionally reports:

```text
waiting
entered
partial_targets
target_completions
stopped
invalidated
net_pnl
average_r
```

Absent optional financial metrics are rendered as `na` rather than zero in text output.

## Public API

The following analytics contracts and builders are exported from `apex.application`:

```text
HoldingTimeBand
PaperLifecycleAnalytics
PaperLifecycleTradeRecord
RiskMultipleBand
build_paper_lifecycle_analytics
paper_lifecycle_analytics_payload
```

## Compatibility

- Partial intake/runtime inputs produce zero operational counts.
- Missing trade snapshots produce an empty trade list.
- Missing financial fields remain `null`.
- Historical trade payloads without scanner or gainer metadata remain valid.
- Historical trades without `market_type` remain assigned to futures.
- Output maps and trade records are sorted deterministically.
