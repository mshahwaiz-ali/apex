# S10 Empirical Calibration and Stability Analysis

## Status

S10 implementation is functionally complete and awaiting the reported local quality gate.

This stage provides deterministic parameter-candidate comparison and audit artifacts. It does not establish profitability, funded-account eligibility, production readiness, or real-money safety.

## Implemented scope

- One optimization variable group is evaluated at a time.
- Candidate performance is compared with an explicit baseline.
- Train and validation results determine candidate selection.
- Final-test results are excluded from selection and evaluated only after a candidate passes train, validation, and stability gates.
- A failed final-test audit is retained without rewriting the earlier selection decision.
- Minimum sample, expectancy, profit-factor, drawdown, symbol-dependency, and optional strategy-dependency rules are enforced by the optimization engine.
- Additional stability gates cover symbol count, market-regime count, score-band count, and maximum concentration shares.
- Empirical reports contain deterministic SHA-256 integrity hashes.
- Reports are written atomically, reloaded, and hash-verified before CLI success is reported.
- Tampered reports are rejected.
- Historical spot backtest payloads can be adapted into canonical `PerformanceSummary` inputs.
- Historical futures payloads can be adapted directly or by requested train, validation, or final-test split.
- Public optimization exports expose the empirical report and historical adapter APIs.

## Command

```bash
apex optimize empirical-calibrate \
  --input data/optimization/s10-input.json \
  --output data/optimization/s10-report.json
```

Existing output is not overwritten unless `--force` is supplied.

## Input sections

The input JSON requires:

- `split`: chronological train, validation, and out-of-sample boundaries;
- `run_config`: variable group, minimum samples, expectancy delta, drawdown tolerance, and dependency limits;
- `parameter_set`: candidate identifier, optimization group, and proposed values;
- `train_baseline` and `train_candidate` performance reports;
- `validation_baseline` and `validation_candidate` performance reports.

Optional sections:

- `final_test_baseline` and `final_test_candidate`;
- `stability_policy` for symbol, regime, and score-band coverage and concentration limits.

## Selection semantics

A candidate reaches final-test audit only when:

1. train comparison passes;
2. validation comparison passes;
3. validation sample distribution passes stability gates.

Final-test performance is recorded with `used_for_selection: false`.

A selected candidate with no final-test inputs remains explicitly unaudited. It must not be described as out-of-sample validated.

## Integrity

The output contains a deterministic `report_sha256`. The command writes atomically, immediately reloads the artifact, and verifies the complete payload hash before reporting completion.

## Validation boundary

S10 is not formally closed until focused Ruff, strict mypy, focused pytest, and the complete repository quality gate are run locally and their exact outputs are recorded.
