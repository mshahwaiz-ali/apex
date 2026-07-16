# Phase 6 production analytics

The futures paper pipeline now persists structured Phase 6 risk-decision diagnostics alongside the existing Phase 4 and Phase 5 analytics.

The shared diagnostics payload is emitted to:

- futures intake JSONL audit records;
- futures pipeline JSONL audit records;
- `paper scheduled-futures-pipeline --output json`.

## Run-level summary

`diagnostics.phase6_summary` contains:

- observed, approved and rejected decision counts;
- rejection-code totals;
- rejection codes by scanner category;
- rejection codes by selected strategy when a stable Phase 5 selected identity is available;
- approved counts by strategy and direction;
- stop-quality band counts;
- required-leverage band counts;
- take-profit count distribution;
- average required leverage, account risk percentage and stop distance percentage.

The leverage bands are:

- `1_5x`;
- `5_10x`;
- `10_20x`;
- `above_20x`.

## Per-analysis payload

`diagnostics.phase6_analyses` uses the same canonical symbol/scanner keys as earlier phases:

```text
BTC/USDT:NORMAL_MARKET
BTC/USDT:GAINER
```

Rejected analyses include structured rejection codes, aligned human-readable reasons, the selected strategy when recoverable, and the existing detailed risk-rejection geometry.

Approved analyses include entry geometry, stop quality, position sizing, leverage and liquidation geometry, target count, management-policy count and warning count.

## Non-fabrication behavior

The aggregator counts only stable enums and explicit contract fields. It does not parse free-form reason text. Strategy attribution for rejected decisions is emitted only when the Phase 5 payload contains an explicit selected candidate identity.