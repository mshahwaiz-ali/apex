# Vision and Scope

## Product vision

Apex Trading Agent is a deterministic Python system for finding aggressive but structured crypto opportunities near the current market price.

For every analyzed market, Apex must return one of:

- `LONG`
- `SHORT`
- `NO_TRADE`

A valid trade decision includes a practical entry zone, structural invalidation, stop-loss, take-profit targets, risk-to-reward, position sizing, leverage constraints, evidence, contradictions, and warnings.

## Design philosophy

### Aggressive but structured

Apex should actively search for early or near-market entries. Aggressive execution never removes the requirement for a defined thesis, measurable loss, logical target, and explicit invalidation.

### Deterministic before intelligent

Core trade decisions remain reproducible, testable, explainable, and independent of paid AI services. Optional intelligence layers may summarize or rank evidence later, but must not silently replace deterministic safety rules.

### Evidence over indicator voting

Decisions combine market structure, liquidity behavior, momentum, volatility, volume, location, multi-timeframe context, and risk geometry. No single indicator controls a trade.

## Initial operating scope

- Liquid cryptocurrency markets
- Public live and historical data
- Single-symbol analysis
- Normal-market and fast-gainer scanning
- Multi-timeframe analysis: `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `4h`
- Long, short, and no-trade decisions
- Backtesting and forward paper trading
- JSON, text, SQLite, JSONL, CSV, or Parquet outputs as appropriate
- Testnet execution only after readiness gates pass

## Non-goals

- Guaranteed profitability
- Autonomous real-money execution by default
- Martingale sizing
- Unlimited leverage
- Averaging into losses without strict rules
- Paid LLM dependence
- Heavy web-framework coupling
- Provider-specific logic spread through the domain layer

## Success criteria

Apex is successful when it produces repeatable risk-adjusted expectancy across symbols and regimes, survives fees and slippage, limits drawdown and liquidation risk, and explains every decision well enough to audit later.
