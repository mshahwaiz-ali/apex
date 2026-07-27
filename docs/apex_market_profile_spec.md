# Apex Market Profile Specification

`MarketBehaviorProfile` is point-in-time and `observe_only`.

| Field | Definition | Input / lookback | Leakage and missing policy |
|---|---|---|---|
| Liquidity median | Median closed-candle quote volume | Up to 120 decision-frame bars | `null` if quote volume is absent |
| Volatility class/percentile | ATR and candle-range percentile against prior observations | ATR 14, up to 120 baseline bars | Only bars closed by decision time |
| Directional efficiency | Absolute net close move divided by sum of absolute close-to-close moves | Up to 120 closed bars | `null` with fewer than two bars |
| Chop score | `1 - directional_efficiency` | Same window | Diagnostic only |
| Wick noise | Mean non-body range divided by full candle range | Up to 120 non-zero-range bars | `null` when unavailable |
| False-break frequency | Share of observed boundary breaks that close back inside the prior range | Closed decision-frame history | `null` without eligible breaks; observe-only |
| Execution friction | Normalized spread/cost/noise pressure | Available precision, spread, costs, and closed volatility | Missing components remain unavailable; observe-only |
| Listing maturity | Whole/fractional days from exchange onboarding to decision time | Point-in-time contract metadata | `null` when onboarding history is unavailable |
| Cohort | Deterministic classification of history, volatility, efficiency, and wick noise | Same point-in-time values | Empirical candidate; never a production gate without promotion |

Future candidates include pullback depth, stop-run frequency, and
comparable-setup MFE/MAE. They must declare formula, inputs, lookback, missing
policy, and prefix-invariance tests before implementation.
