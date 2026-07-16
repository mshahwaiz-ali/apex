# Sealed P1 Review Evidence

## Purpose

The P1 review report is already self-hashed, but it is generated from several external evidence files. The sealed P1 review artifact binds the review to the exact bytes used for:

- the P1 review report;
- the historical edge profile;
- the forward-paper edge profile;
- the forward-paper daily report;
- the paper-trade store.

The artifact is offline, deterministic, path-independent, and explicitly non-authorizing.

## Seal a P1 review

```bash
apex paper p1-review-seal \
  --review-report data/reports/p1-review.json \
  --historical-profile data/reports/historical-profile.json \
  --forward-profile data/reports/forward-profile.json \
  --daily-report data/reports/paper-daily.json \
  --paper-store data/paper_trading/trades.json \
  --output data/reports/p1-review-sealed.json
```

Existing output paths are rejected unless `--force` is supplied.

## Verify exact source evidence

```bash
apex paper p1-review-seal-verify \
  --artifact data/reports/p1-review-sealed.json \
  --review-report data/reports/p1-review.json \
  --historical-profile data/reports/historical-profile.json \
  --forward-profile data/reports/forward-profile.json \
  --daily-report data/reports/paper-daily.json \
  --paper-store data/paper_trading/trades.json
```

Machine-readable output:

```bash
apex paper p1-review-seal-verify \
  --artifact data/reports/p1-review-sealed.json \
  --review-report data/reports/p1-review.json \
  --historical-profile data/reports/historical-profile.json \
  --forward-profile data/reports/forward-profile.json \
  --daily-report data/reports/paper-daily.json \
  --paper-store data/paper_trading/trades.json \
  --output json
```

## Verification outcomes

### `verified`

Every source filename and SHA-256 matches the sealed artifact, the artifact self-hash is valid, and `execution_authorized` remains false.

Exit code: `0`.

### `source_changed`

At least one source filename or SHA-256 differs from the sealed evidence.

Exit code: `2`.

The text output identifies changed-content sources under `mismatched` and filename-only changes under `renamed`.

## Artifact guarantees

The sealed artifact contains:

- schema version;
- P1 review report hash;
- P1 review state;
- stable source filenames;
- exact SHA-256 for all five evidence files;
- complete artifact SHA-256;
- `execution_authorized: false`.

Absolute paths are excluded from artifact identity. Copying identical evidence files to another machine or directory therefore preserves artifact identity when filenames remain the same.

## Safety boundary

A valid sealed P1 artifact proves evidence integrity only. It does not authorize:

- testnet execution;
- funded-account operation;
- production trading;
- real-money execution;
- autonomous order placement.
