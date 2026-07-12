# Phase G/H/I Remaining Foundations

This note records the combined remaining-phase foundation slice.

## Phase G Optimization

Added:

- `performance_from_backtest_study(study)`
- `compare_backtest_studies(baseline, candidate, ...)`
- symbol-dependency rejection
- optional strategy-dependency rejection

Optimization still enforces one variable group at a time through the existing
`OptimizationRunConfig.variable_group` and `CandidateParameterSet.group`
contract.

## Phase H Paper Trading

Added:

- `PaperReport`
- `BacktestPaperComparison`
- `generate_paper_report(...)`
- `compare_backtest_to_paper(...)`

The existing JSON store remains the lifecycle persistence mechanism. Reports
are derived from stored paper trades and do not mutate trade state.

## Phase I Optional Real Exchange Testnet

No real exchange adapter was enabled in this slice.

Reason:

- The plan requires Phase I to start only after Phases A-H pass.
- The project still needs deeper full-pipeline historical replay and extended
  paper-trading recovery before a real testnet provider should be introduced.
- Mainnet execution remains unsupported.

Current execution behavior remains simulated/local only.
