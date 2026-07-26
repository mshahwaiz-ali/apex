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
- Keep canonical, conditional, opportunity, and shadow populations separate.
- Mark calibration and promotion non-authoritative when required populations are
  absent.

## Validation design

Use expanding walk-forward folds, a final untouched time holdout, symbol and
behavioral-cohort holdouts, and purge/embargo at least as long as the maximum
label horizon. Test neighboring parameters, higher costs, and results excluding
the best symbol and month.

## Reporting

Report decision funnel, fills, expiries, invalidations, win/loss/breakeven,
expectancy in R, net expectancy, profit factor, payoff, drawdown, losing streak,
MFE/MAE, holding time, calibration, fold/cohort breakdowns, sensitivity, and
uncertainty intervals.

## Promotion

Balanced-edge promotion requires an untouched 95% bootstrap lower bound for net
expectancy above zero, profit factor above one, drawdown within the declared
risk budget, fold/cohort stability, and no dependence on the best symbol or
month. PBO is unavailable without multiple fold-level configuration vectors.
