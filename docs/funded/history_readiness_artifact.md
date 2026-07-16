# Sealed History-Backed Funded-Readiness Evidence

## Purpose

The aggregate-history-funded-readiness path combines verified operator inputs with the canonical P1 aggregate history review.

The sealed history-backed readiness artifact binds the exact bytes of:

- the funded-readiness input document;
- the aggregate P1 history review;
- the emitted funded-readiness report.

The artifact is deterministic, path-independent, offline, and explicitly non-authorizing.

## Generate the readiness report

```bash
apex funded-readiness-from-history data/reports/funded-readiness-input.json \
  --history-review data/reports/p1-history-review.json \
  --report data/reports/funded-history-readiness-report.json \
  --output json
```

## Seal the evidence

```bash
apex funded-history-readiness-seal \
  --input data/reports/funded-readiness-input.json \
  --history-review data/reports/p1-history-review.json \
  --report data/reports/funded-history-readiness-report.json \
  --output data/reports/funded-history-readiness-sealed.json
```

Existing output paths are rejected unless `--force` is supplied.

## Verify exact source evidence

```bash
apex funded-history-readiness-seal-verify \
  --artifact data/reports/funded-history-readiness-sealed.json \
  --input data/reports/funded-readiness-input.json \
  --history-review data/reports/p1-history-review.json \
  --report data/reports/funded-history-readiness-report.json
```

Machine-readable output:

```bash
apex funded-history-readiness-seal-verify \
  --artifact data/reports/funded-history-readiness-sealed.json \
  --input data/reports/funded-readiness-input.json \
  --history-review data/reports/p1-history-review.json \
  --report data/reports/funded-history-readiness-report.json \
  --output json
```

## Verification outcomes

### `verified`

Every source filename and SHA-256 matches the sealed artifact, the artifact self-hash is valid, and `execution_authorized` remains false.

Exit code: `0`.

### `source_changed`

At least one source filename or SHA-256 differs from the sealed evidence.

Exit code: `2`.

Text output lists changed-content sources under `mismatched` and filename-only changes under `renamed`.

## Artifact guarantees

The artifact contains:

- schema version;
- provider identity;
- readiness decision;
- aggregate-history readiness state;
- stable source filenames;
- exact source SHA-256 values;
- complete artifact SHA-256;
- `execution_authorized: false`.

A report with `ready: true` cannot be sealed against an aggregate history review whose `ready_for_funded_review` value is false.

Absolute paths are excluded from artifact identity. Copying identical files to another machine or directory preserves identity when filenames remain unchanged.

## Safety boundary

A valid artifact proves evidence integrity only. It does not authorize:

- autonomous order placement;
- funded-account execution;
- production trading;
- real-money execution;
- bypassing provider rules or manual review.
