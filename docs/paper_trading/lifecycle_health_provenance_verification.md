# Paper Lifecycle-Health Provenance Verification

## Purpose

`apex paper lifecycle-health-verify` checks a persisted lifecycle-health artifact against the scheduler JSONL log declared by that artifact.

The command is offline and deterministic. It performs no market-data request, paper-trade mutation, exchange operation, or execution authorization.

## Command

```bash
apex paper lifecycle-health-verify \
  --artifact data/reports/futures-lifecycle-health.json \
  --source-log data/paper_trading/scheduler/logs/pipeline-futures.jsonl
```

Machine-readable output:

```bash
apex paper lifecycle-health-verify \
  --artifact data/reports/futures-lifecycle-health.json \
  --source-log data/paper_trading/scheduler/logs/pipeline-futures.jsonl \
  --output json
```

## Verification checks

The verifier first reloads the lifecycle-health artifact and validates its own report hash. It then checks:

- scheduler log filename;
- exact declared JSONL line number;
- source run identifier;
- source market type;
- selected source-record SHA-256;
- lifecycle-analytics SHA-256;
- complete scheduler-log SHA-256;
- the artifact safety field `execution_authorized`.

## Statuses

### `verified`

The artifact is internally valid and the supplied scheduler log exactly matches the complete source evidence captured when the artifact was created.

Exit code: `0`.

### `source_log_changed`

The selected source record, analytics payload, and run identity remain valid, but the supplied log no longer has the same complete-file identity or filename. A normal append-only scheduler update can produce this status while preserving the original record.

This status does not mean the artifact is fraudulent, but it means the complete current log is no longer byte-identical to the captured source log.

Exit code: `2`.

### `source_record_invalid`

The declared source line is missing, malformed, changed, has different analytics, has a different run or market identity, or the artifact contains forbidden execution authorization.

The artifact must not be used as verified forward-paper evidence.

Exit code: `2`.

## Safety boundary

Successful provenance verification confirms evidence integrity only. It does not establish:

- historical edge;
- positive forward expectancy;
- testnet readiness;
- funded-account eligibility;
- production readiness;
- permission to execute orders;
- real-money safety.
