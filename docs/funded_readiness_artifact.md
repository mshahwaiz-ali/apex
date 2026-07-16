# Sealed Funded-Readiness Evidence

## Purpose

The funded-readiness review produces a manual R1 decision from provider limits, forward-validation evidence, account-policy state, lockout checks, execution checklists, and kill-switch state.

The sealed funded-readiness artifact binds that decision to the exact bytes of:

- the funded-readiness input document;
- the emitted funded-readiness report.

The artifact is deterministic, path-independent, offline, and explicitly non-authorizing.

## Generate the readiness report

```bash
apex funded-readiness-review data/reports/funded-readiness-input.json \
  --report data/reports/funded-readiness-report.json \
  --output json
```

## Seal the review evidence

```bash
apex funded-readiness-seal \
  --input data/reports/funded-readiness-input.json \
  --report data/reports/funded-readiness-report.json \
  --output data/reports/funded-readiness-sealed.json
```

Existing output paths are rejected unless `--force` is supplied.

## Verify exact source evidence

```bash
apex funded-readiness-seal-verify \
  --artifact data/reports/funded-readiness-sealed.json \
  --input data/reports/funded-readiness-input.json \
  --report data/reports/funded-readiness-report.json
```

Machine-readable output:

```bash
apex funded-readiness-seal-verify \
  --artifact data/reports/funded-readiness-sealed.json \
  --input data/reports/funded-readiness-input.json \
  --report data/reports/funded-readiness-report.json \
  --output json
```

## Verification outcomes

### `verified`

The input and report filenames and SHA-256 hashes match the sealed artifact, the artifact self-hash is valid, and `execution_authorized` remains false.

Exit code: `0`.

### `source_changed`

At least one source filename or SHA-256 differs from the sealed evidence.

Exit code: `2`.

Text output lists content changes under `mismatched` and filename-only changes under `renamed`.

## Artifact guarantees

The sealed artifact contains:

- schema version;
- provider identity;
- readiness decision;
- stable input and report filenames;
- exact source SHA-256 values;
- complete artifact SHA-256;
- `execution_authorized: false`.

Absolute paths are excluded from artifact identity. Copying identical files to another machine or directory preserves identity when filenames remain unchanged.

## Safety boundary

A readiness result of `ready: true` means the configured manual funded-readiness checks passed. It does not authorize:

- autonomous order placement;
- funded-account execution;
- production trading;
- real-money execution;
- bypassing provider rules or manual review.
