# Apex Trade Analysis Methodology

## Authority and objective

This document is the implementation authority for Apex trade discovery and analysis.
`apex scan` and `apex analyze SYMBOL` must use the same analysis core after symbol
selection. Apex finds current or developing long and short hypotheses with controlled
structural risk; it does not guarantee outcomes, force trades, choose leverage, allocate
wallet capital, or place orders.

The preferred opportunity has the strongest supported movement relative to structural
risk. Raw percentage movement, indicator count, and uncalibrated confidence are not edge.

## Controlling research rules

- Murphy: structure, polarity, volume confirmation, top-down context, and measured
  objectives define the technical thesis.
- Nison: completed candles are contextual timing evidence. They never create targets or
  approve a trade without compatible structure, invalidation, and target room.
- Douglas: risk is defined before execution; confidence describes process quality unless
  untouched out-of-sample calibration supports a probability.
- Bulkowski: chart-pattern definitions are hypotheses. Equity performance statistics are
  not transferred to crypto without chronological testing.
- Multiple-timeframe analysis assigns context, setup, trigger, risk, and management roles;
  timeframes are not equal votes.

## Canonical pipeline

```text
historical universe -> tradability -> discovery lanes -> shortlist
-> shared closed-candle analysis -> structure and regime
-> independent long and short hypotheses -> strategy routing -> setup maturity
-> current and alternative entries -> invalidation and stop -> structural targets
-> duration and lifecycle -> quality and calibrated edge -> reasoned output
```

No score may repair a hard blocker. Missing optional evidence lowers quality or remains
unavailable. Missing mandatory structure, invalidation, stop geometry, or realistic target
room blocks execution.

## Discovery policy

Tradability gates are liquidity, spread, data freshness/history, exchange metadata, and
execution quality. Minimum movement is not a tradability gate. Discovery maintains
independent coverage for:

1. trend continuation;
2. compression and expansion;
3. fresh break;
4. fast mover;
5. range or liquidity rejection;
6. benchmark-relative strength or weakness;
7. developing setups.

Lane tags explain why a symbol received expensive analysis; they never approve a trade.
Unused lane capacity may be filled by global opportunity quality.

## Canonical strategy families

| Family | Required context | Trigger | Default expiry |
|---|---|---|---:|
| Trend pullback | Established directional structure | Completed continuation or rejection | 8 setup bars |
| Break continuation | Fresh accepted structural break | Close/acceptance with participation | 3 trigger bars |
| Break retest | Confirmed break and held polarity | Completed retest/reclaim | 6 setup bars |
| Compression expansion | Contraction at a defined boundary | Expansion close or held first retest | 6 setup bars |
| Range rejection | Stable range and boundary location | Completed rejection | 6 setup bars |
| Failed break/reclaim | Break cannot hold | Close back through the boundary | 6 setup bars |
| Liquidity sweep reversal | Sweep at meaningful structure | Completed reclaim | 6 setup bars |

Momentum, first-pullback, VWAP, exhaustion, and scalp describe modifiers, entry models, or
horizons. Existing strategy identifiers remain compatibility aliases during schema v2.

## Entry, risk, target, and lifecycle rules

- Evaluate immediate, aggressive, pullback, retest, reclaim, rejection, and developing
  entries independently. A preferred entry must not hide a valid current entry.
- Public maturity distinguishes waiting for close/break/retest/reclaim, available,
  aggressive, late, missed, expired, failed, and structurally invalidated states.
- Invalidation names the governing structure and failure event. Apply one explicit noise
  buffer to derive the stop.
- Targets come from observable structure, liquidity, range/pattern dimensions, or a clearly
  labeled conditional model. A 1R management marker is not a price target.
- Do not force three targets. Every target exposes source, expected movement, risk multiple,
  obstacles, and whether it is conditional.
- Continuation, early-exit, cancellation, and expiry rules are strategy-specific and
  measured in setup/trigger bars.

## Evidence and confidence

Evidence declares family, source, direction, strength, freshness, and independence group.
Correlated evidence receives one capped family contribution. Candlestick evidence is
`CANDLE` family confirmation only.

Public output separates setup quality, execution quality, opportunity geometry, data
quality, and historical edge. Numeric quality is shown as `/100`, never as win probability.
A probability additionally requires an untouched chronological sample, costs, leakage
checks, regime stability, sample size, interval, dataset identity, and calibration version.

## Evaluation standard

Historical evaluation must use production-equivalent closed-candle features, chronological
decisions, no look-ahead, conservative same-candle ambiguity, fees, spread, slippage,
funding when available, partial exits, missed entries, expiry, MFE/MAE, and changing symbol
availability where data exists. Report results by strategy family/version, regime, direction,
liquidity, volatility, entry type, and timeframe combination. Use walk-forward validation
and an untouched test period; do not optimize and evaluate on the same data.

## Public product contract

- `scan`: lane coverage, shortlist reasons, actionable/developing/unavailable/no-trade
  groups, ranked opportunities, and rejection counts.
- `analyze`: why coin, direction, strategy, entry, stop, targets, duration, confidence,
  contradictions, missing evidence, and exact invalidation; retain a valid opposing thesis.
- JSON schema v2 adds canonical methodology fields while retaining schema v1 keys for one
  deprecation cycle.
- Backtest output is research evidence, not a live performance promise.

## Non-goals

No leverage or wallet sizing, order placement, guaranteed win rate, forced trade count,
fixed 10% target, forced current-price entry, candle-only strategy, indicator vote counting,
fabricated derivatives data, or separate scan/analyze analysis engine.
