# P1 Forward Deviation and Lifecycle Review

P1 now includes deterministic daily reporting plus a separate forward-review layer. This layer compares compatible historical and forward-paper segments, audits paper lifecycle integrity, and builds a hash-verified review artifact.

## What P1 currently proves

The implemented controls can establish that a paper segment is dimensionally compatible with its historical baseline, that expectancy and supporting metrics have not degraded beyond configured thresholds, and that stored paper trades have a coherent auditable lifecycle. Reports are deterministic, atomically persisted, protected against silent overwrite, and rejected after payload tampering.

## What remains unproven

P1 does not prove real-market profitability, exchange execution reliability, order reconciliation, production risk safety, or suitability for real-money trading. Positive paper expectancy is insufficient by itself. Production eligibility remains false in the P1 review artifact and requires a separate later decision and execution-readiness evidence.

## Segment compatibility

Historical and forward profiles must have exactly matching dimensions. Intended dimensions include strategy, market type, risk mode where applicable, symbol or symbol group, market regime, and score band. A mismatched segment is rejected rather than compared.

## Deviation thresholds

`ForwardDeviationPolicy` configures maximum acceptable expectancy degradation, profit-factor decline, win-rate decline, drawdown increase, and trade-frequency deviation. Threshold breaches produce explicit rejection reasons and a degraded result. Direction consistency is also required.

## Lifecycle blocking rules

The lifecycle audit is read-only. It detects missing required events, invalid ordering, terminal trades without valid close events, entry after invalidation, stop or target events before entry, invalid timestamps, inconsistent closed percentages, duplicate unique events, holding-limit breaches, and management contradictions. Any lifecycle anomaly blocks a clean forward-validation review.

## Review and production eligibility

The combined review references the daily-report hash, forward-edge validation status, deviation result, lifecycle audit, sample sufficiency, and manual execution usability. Review states distinguish insufficient evidence, failed validation, review-required evidence, and forward validation. The artifact always keeps production eligibility separate and does not authorize automatic trading or promotion.
