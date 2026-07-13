# Phase C Foundation

Source of truth: `docs/plan_2.md`.

This note records the first Phase C foundation pass after the Phase B market-data work.

## Feature Audit Metadata

`FeatureRegistry.audit(candles)` now returns deterministic feature contract metadata for every registered feature result:

```text
group_name
feature_name
minimum_candles
accepts_active_candle
output_shape
missing_data_policy
output_length
finite_values
missing_values
```

This makes the feature registry inspectable without hand-reading every indicator implementation. It does not change feature calculations or strategy behavior.

## Regime Labels

The structural regime classifier now returns more specific labels:

```text
strong_uptrend
weak_uptrend
strong_downtrend
weak_downtrend
stable_range
volatile_range
compression
breakout_expansion
reversal_transition
uncertain
```

Existing broad enum values remain available for compatibility, but new classification output is more actionable for strategy eligibility and reporting.

## Limitations

This is a foundation pass only. The remaining Phase C work still includes broader indicator additions, richer liquidity/trap evidence, expanded fixture scenarios, and strategy eligibility rules driven by the new regime vocabulary.
