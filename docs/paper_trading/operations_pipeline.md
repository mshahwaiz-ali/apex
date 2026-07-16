# Paper Operations Pipeline

Apex provides a paper-only orchestration path that runs automatic opportunity intake before lifecycle advancement under one market-specific lock.

## Commands

Futures:

```bash
apex paper scheduled-futures-pipeline \
  --symbols-file config/symbols.yaml \
  --mode normal \
  --risk-mode STANDARD \
  --wallet-balance 100 \
  --analysis-candles 200 \
  --lifecycle-timeframe 5m \
  --lifecycle-candles 80 \
  --output json
```

Spot:

```bash
apex paper scheduled-spot-pipeline \
  --symbols BTC/USDT,ETH/USDT \
  --account config/spot_account.json \
  --analysis-candles 200 \
  --lifecycle-timeframe 5m \
  --lifecycle-candles 80 \
  --output json
```

Both commands support deterministic text or JSON summaries. The JSON payload includes the complete intake summary, lifecycle result, timestamps, lock path, and audit-log path.

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

Lifecycle advancement retains its existing market-specific cycle lock and log. This provides stage-level evidence while the outer pipeline lock prevents overlap across the complete intake-to-cycle sequence.

The pipeline never places exchange orders. It only mutates the local paper-trade store and writes structured evidence.

## Readiness

`apex paper operations-status` distinguishes:

- `scheduler_ready`: lifecycle cycle logs are fresh and cycle locks are not stale;
- `operations_ready`: cycle, intake, and combined pipeline logs are all fresh, with no stale lock at any stage.

A market is operationally ready only when all three stages are current:

```text
cycle_fresh && intake_fresh && pipeline_fresh
```

This prevents a healthy lifecycle scheduler from masking a stopped scanner or intake stage.

## Scheduler Integration

A scheduler should invoke one complete market pipeline at a time. Do not run a separate intake command concurrently with the same market pipeline. Futures and spot may run independently because their locks and audit paths are separate.

Recommended cadence for active forward-paper validation:

```text
futures pipeline: every 5 minutes
spot pipeline: every 15 minutes
operations-status: every 5 minutes
```

Cadence remains configurable and should match provider limits and selected analysis timeframes.

Example cron entries:

```cron
*/5 * * * * cd /opt/apex && .venv/bin/apex paper scheduled-futures-pipeline --output json >> data/paper_trading/cron-futures-pipeline.log 2>&1
2-59/15 * * * * cd /opt/apex && .venv/bin/apex paper scheduled-spot-pipeline --symbols BTC/USDT,ETH/USDT --account config/spot_account.json --output json >> data/paper_trading/cron-spot-pipeline.log 2>&1
*/5 * * * * cd /opt/apex && .venv/bin/apex paper operations-status --output json >> data/paper_trading/cron-operations-status.log 2>&1
```

## Failure Semantics

- Existing non-stale pipeline lock: skip the overlapping invocation with exit code zero.
- Stale pipeline lock: recover using the existing stale-lock protocol.
- Intake market mismatch: fail before lifecycle advancement.
- Cycle market mismatch: fail before writing a successful pipeline audit entry.
- Invalid stale-lock duration: fail before acquiring a lock.
- Empty scan: valid zero-candidate intake followed by a normal lifecycle cycle.
- Repeated scan: stable deduplication prevents duplicate paper trades.
- Provider failures remain visible in lifecycle results and pipeline summaries.
