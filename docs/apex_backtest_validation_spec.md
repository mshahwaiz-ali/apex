# Apex Backtest Validation Specification

## Dataset identity

Every campaign records methodology/config versions, dataset fingerprint,
point-in-time universe, behavioral cohorts, timeframes, costs, attempted
configurations, purge horizon, embargo, and final-test status.

## Replay rules

- Generate decisions using closed information available at the decision time.
- Freeze the setup, trigger, invalidation, chase boundary, expiry, and version.
- Use conservative intrabar ordering when stop and target are both touched.
- Apply explicit entry/exit fees and slippage once.
- Apply funding events strictly after entry through exit against remaining
  position size; keep manual funding as a separately labeled stress override.
- Keep canonical, conditional, opportunity, and shadow populations separate.
- Mark calibration and promotion non-authoritative when required populations are
  absent.

## Validation design

Use expanding walk-forward folds, a final untouched time holdout, symbol and
behavioral-cohort holdouts, and purge/embargo at least as long as the maximum
label horizon. Test neighboring parameters, higher costs, and results excluding
the best symbol and month.

Configuration selection uses validation folds only. The final holdout unlocks
once after selection. Canonical no-trade decisions are retained in the funnel as
zero-return decisions, but the minimum promotion sample counts only executed
canonical outcomes. Shadow outcomes never enter canonical expectancy.

## Reporting

Report decision funnel, fills, expiries, invalidations, win/loss/breakeven,
expectancy in R, net expectancy, profit factor, payoff, drawdown, losing streak,
MFE/MAE, holding time, calibration, fold/cohort breakdowns, sensitivity, and
uncertainty intervals.

Probability reporting requires pre-outcome probabilities and binary labels.
When available, report reliability bins, Brier score decomposition, Brier skill,
and expected calibration error. A rule/rank score is not a probability.

## Promotion

Balanced-edge promotion requires an untouched 95% bootstrap lower bound for net
expectancy above zero, profit factor above one, drawdown within the declared
risk budget, fold/cohort stability, and no dependence on the best symbol or
month. PBO is unavailable without multiple fold-level configuration vectors.
It is also unavailable when those vectors have no cross-sectional variation.
