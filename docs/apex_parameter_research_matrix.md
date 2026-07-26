# Apex Parameter Research Matrix

Runtime configuration now emits a `ResolvedParameter` record for every leaf.

| Parameter group | Current source | Candidate research | Promotion / rollback |
|---|---|---|---|
| Fees and slippage | Conservative configured market profile | Account tier and higher-cost stresses | Promote only with explicit source; roll back on cost under-modeling |
| Indicator periods | Existing production profiles by timeframe role | Neighboring periods, training-only | Untouched stability; no isolated best value |
| Market-environment thresholds | Existing production values | Cohort-normalized distributions | Positive net effect without cohort harm |
| Geometry minima/caps | Existing lane settings | Strategy/lane training distributions | Preserve fatal safety gates |
| HTF consequences | Existing production values | Severity-specific shadow variants | No critical-opposition leakage |
| Ranking weights | Existing production values | Saturation and redundancy experiments | Stable ordering and net utility |
| Behavior cohort cutoffs | Empirical candidates | Training quantiles | Remain observe-only until holdouts pass |

Production promotion requires provenance
`promoted_after_out_of_sample_validation`; source or internet values alone are
not sufficient.
