# S3 — Initial Spot Strategies

## Status

Implementation is present on `main`. The complete local quality gate remains pending.

S3 converts normalized S2 structure and regime outputs into independently testable spot strategy candidates. It intentionally does not perform position sizing, capital allocation, entry-ladder construction, target construction, or lifecycle management; those remain S4 responsibilities.

## Implemented strategies

The deterministic router evaluates strategies in the roadmap order:

1. `higher_timeframe_trend_pullback`
2. `breakout_retest`
3. `accumulation_range_breakout`
4. `liquidity_sweep_daily_recovery`
5. `relative_strength_leader_pullback`
6. `post_capitulation_recovery`

The first approved candidate in that fixed order becomes the selected candidate. Every evaluator remains callable and testable independently.

## Candidate contract

Every `SpotStrategyCandidate` includes:

- strategy identifier;
- `APPROVE`, `WATCH`, or `REJECT` decision;
- research eligibility;
- explicit thesis;
- structural invalidation price;
- evidence;
- rejection reasons;
- warnings.

The contracts contain no leverage, margin, liquidation, short-selling, quantity, notional, or allocation fields.

## Shared safety gates

Standard S3 strategies reject or watch when:

- the broad-market regime blocks new entries;
- the regime is `RISK_OFF` or `CAPITULATION`;
- the asset is terminally extended;
- the asset is in a downside-risk extension state.

The post-capitulation recovery evaluator is exempt from the standard capitulation rejection only so it can evaluate recovery evidence. It remains explicitly `PAPER_ONLY` and carries an experimental warning.

## Configuration

`config/spot_strategies.yaml` and `SpotStrategyConfig` define:

- minimum relative strength;
- normal and breakout volume ratios;
- maximum controlled pullback depth;
- maximum accumulation range width;
- invalidation buffer;
- experimental strategy enablement.

Configuration is provider-independent and validated through Pydantic.

## Tests

Focused tests cover:

- independent approval of each standard strategy;
- thesis and invalidation output;
- deterministic router priority;
- broad-market risk-off rejection;
- terminal-extension rejection;
- paper-only post-capitulation recovery;
- configuration loading and validation;
- absence of sizing fields from strategy candidates.

The full repository quality gate has not been run in the GitHub connector environment. S3 must not be declared quality-gate complete until these commands pass locally:

```bash
ruff format .
ruff check .
mypy src
pytest
```

Any failures from that gate must be repaired before S4 begins.
