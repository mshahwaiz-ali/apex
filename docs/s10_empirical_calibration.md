# S10 Empirical Calibration

## Purpose

`apex optimize empirical-calibrate` evaluates one candidate parameter set against a baseline using train and validation reports only. Final-test reports are attached only after the candidate passes train, validation, and stability gates.

This command does not edit production configuration and does not establish profitability, funded eligibility, production readiness, or real-money safety.

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

Performance objects use the same normalized metrics accepted by the optimization engine: total trades, win rate, expectancy, profit factor, maximum drawdown, net profit, and trade-count distributions by symbol, strategy, regime, and score band.

## Selection rules

A candidate is selected for final-test audit only when:

1. train comparison passes;
2. validation comparison passes;
3. validation samples pass symbol, regime, and score-band stability gates.

Final-test performance is never used to select parameters. The report records `used_for_selection: false` explicitly.

## Integrity

The output contains a deterministic `report_sha256`. The command writes atomically, immediately reloads the artifact, and verifies the complete payload hash before reporting completion. Tampered or malformed reports fail explicitly.

## Boundary

S10 calibration reports are research artifacts. Parameter changes must remain reviewable and must not be applied automatically to production configuration.
