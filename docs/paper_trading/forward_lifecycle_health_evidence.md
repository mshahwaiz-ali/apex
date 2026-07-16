# N4.8 — Forward-Paper Lifecycle Health Evidence

## Purpose

N4.8 evaluates the latest successful scheduled paper-pipeline run and produces a deterministic health assessment for forward-paper review.

This gate measures operational and lifecycle evidence only. It does not authorize testnet execution, funded trading, or real-money execution.

## Command

```bash
apex paper lifecycle-health --market futures
```

JSON output and a persisted report can be requested with:

```bash
apex paper lifecycle-health \
  --market futures \
  --output json \
  --report data/reports/futures-lifecycle-health.json
```

Existing reports are not overwritten unless `--force-report` is supplied.

## Health policy

The policy evaluates:

- minimum terminal-trade sample size;
- provider failure rate;
- missing-candle rate;
- persistence failure rate;
- invalidation rate;
- unfilled terminal rate;
- average realized R multiple;
- realized net PnL;
- presence of realized performance evidence.

All thresholds are explicit CLI inputs and are serialized into the report.

## Artifact integrity

Lifecycle-health artifacts use schema version 2 and contain:

- source run identifier;
- market type;
- source completion timestamp;
- stable source log filename;
- exact source JSONL line number;
- SHA-256 of the selected source record;
- SHA-256 of the complete source log;
- SHA-256 of the lifecycle analytics payload;
- exact evaluation policy;
- evaluated health result;
- lifecycle analytics snapshot;
- SHA-256 of the complete report payload.

Absolute local paths are excluded from artifact identity so identical evidence produces the same artifact across machines.

## Safety boundary

Every artifact includes:

```json
{
  "execution_authorized": false
}
```

A healthy lifecycle report means only that the configured forward-paper operational gate passed. Historical viability, out-of-sample evidence, forward expectancy, execution readiness, and capital eligibility remain separate gates.
