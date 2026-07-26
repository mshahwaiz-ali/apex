# Apex Root-Cause Report

| Finding | Evidence | Impact | Confidence | Remediation / validation |
|---|---|---:|---:|---|
| Retired methodology identity remained public | Runtime and README referenced a deleted document | Reproducibility drift | High | Replaced by the quality-recovery audit and content identity |
| Live/replay optional-evidence parity is incomplete | Historical provider intentionally rejects ticker and derivatives calls | Historical estimates may not represent live evidence coverage | High | Preserve degradation labels; add aligned archives before parity claims |
| Backtest used symmetric built-in costs | `BacktestConfig` defaults differed from configured geometry costs | Net expectancy could be inconsistent | High | Consume explicit market entry/exit fees and slippage; regression-test each component |
| PBO population was insufficient | One training/final comparison produced a binary diagnostic | Misleading statistical confidence | High | Return unavailable until fold-level configuration vectors exist |
| Regime hysteresis was not stateful in production | Guard existed without a persisted previous-state input | Rapid classification changes remain possible | Medium | Add explicit point-in-time state lineage before gating |
| Name-derived archetypes coexist with behavioral profiling | BTC/ETH special cases exist in legacy market intelligence | Cohort labels can encode names instead of behavior | High | Use observe-only dynamic cohorts, then validate replacement in shadow |
| Many thresholds have no machine-readable provenance | YAML validates values but did not state origin | Tuning and rollback are hard to audit | High | Emit `ResolvedParameter` records for every resolved leaf |
| Rule scores may saturate | Several ranking components clamp to 100 | Reduced ranking resolution | Medium | Measure saturation by strategy/cohort before changing weights |

No finding proves a profitable strategy. Each remediation is an experiment whose
promotion depends on untouched net performance and stability.
