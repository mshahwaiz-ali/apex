# N4.9 — Lifecycle-Health Source Verification

## Status

Implemented on `main`; local Ruff, strict mypy, pytest, and diff validation remain to be reported for this batch.

## Implemented behavior

- Added deterministic offline verification of persisted lifecycle-health artifacts against scheduler JSONL evidence.
- Artifact self-hash verification remains mandatory before source verification begins.
- Verification checks the declared scheduler filename, source line number, run ID, market type, source-record hash, analytics hash, and complete source-log hash.
- Added stable statuses:
  - `verified`;
  - `source_log_changed`;
  - `source_record_invalid`.
- Append-only changes after the preserved source record are distinguished from mutations to the declared record.
- Missing, empty, malformed, non-object, identity-mismatched, and analytics-mismatched source records fail explicitly.
- An artifact with `execution_authorized: true` is rejected as invalid evidence.
- Added `apex paper lifecycle-health-verify` with deterministic text and JSON output.
- Verified evidence exits with code `0`; changed or invalid evidence exits with code `2`.
- Invalid output selection fails before artifact or source verification.
- Registered the command through the corrected CLI overlay.
- Added focused unit and CLI coverage for exact verification, append-only log changes, changed analytics, wrong filenames, missing lines, malformed JSON, command registration, JSON output, exit codes, and fail-fast output validation.
- Added operator documentation in `docs/paper_lifecycle_health_verification.md`.

## Safety boundary

N4.9 proves only that a stored lifecycle-health artifact is internally valid and can be tied back to declared scheduler evidence.

It does not establish historical edge, forward expectancy, funded eligibility, testnet readiness, production readiness, exchange-execution permission, or real-money safety.
