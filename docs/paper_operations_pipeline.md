# Paper Operations Pipeline

Apex now has a paper-only orchestration primitive that runs automatic opportunity intake before lifecycle advancement under one market-specific lock.

## Sequence

```text
scan and plan
  -> qualify and deduplicate intake candidates
  -> persist accepted paper trades
  -> advance eligible open trades with closed candles
  -> append one pipeline audit record
```

Futures and spot use separate locks and logs:

```text
data/paper_trading/scheduler/locks/pipeline-futures.lock
data/paper_trading/scheduler/locks/pipeline-spot.lock
data/paper_trading/scheduler/logs/pipeline-futures.jsonl
data/paper_trading/scheduler/logs/pipeline-spot.jsonl
```

The pipeline never places exchange orders. It only mutates the local paper-trade store and writes structured evidence.

## Readiness

`apex paper operations-status` now distinguishes:

- `scheduler_ready`: lifecycle cycle logs are fresh and cycle locks are not stale;
- `operations_ready`: cycle, intake, and combined pipeline logs are all fresh, with no stale lock at any stage.

A market is operationally ready only when all three stages are current:

```text
cycle_fresh && intake_fresh && pipeline_fresh
```

This prevents a healthy lifecycle scheduler from masking a stopped scanner/intake stage.

## Scheduler Integration

A scheduler should invoke one complete market pipeline at a time. Do not run a separate intake command concurrently with the same market pipeline. Futures and spot may run independently because their lock and audit paths are separate.

Recommended cadence for active forward-paper validation:

```text
futures pipeline: every 5 minutes
spot pipeline: every 15 minutes
operations-status: every 5 minutes
```

Cadence remains configurable and should match provider limits and the selected analysis timeframes.

## Failure Semantics

- Existing non-stale pipeline lock: skip the overlapping invocation.
- Stale pipeline lock: recover using the existing stale-lock protocol.
- Intake market mismatch: fail before lifecycle advancement.
- Cycle market mismatch: fail before writing a successful pipeline audit entry.
- Empty scan: valid zero-candidate intake followed by a normal lifecycle cycle.
- Repeated scan: stable deduplication prevents duplicate paper trades.
