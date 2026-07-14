# S2 — Spot Feature, Structure and Regime Engine

## Status

Implementation is present on `main`. The complete local quality gate remains pending.

## Implemented scope

S2 adds deterministic, higher-timeframe spot analysis without relying on futures geometry or low-timeframe scalp signals.

### Higher-timeframe structure

Supported thesis timeframes:

- `1w`
- `1d`
- `12h`
- `8h`
- `4h`

The engine rejects unsupported lower-timeframe thesis inputs such as `1m`, `3m`, and `5m`.

Each timeframe produces:

- trend classification;
- extension classification;
- ATR-based support zone;
- ATR-based resistance zone;
- ATR-based demand zone;
- deterministic evidence.

### Trend states

- `STRONG_UPTREND`
- `UPTREND`
- `RANGE`
- `DOWNTREND`
- `STRONG_DOWNTREND`

### Extension states

- `NORMAL`
- `EXTENDED`
- `TERMINAL`
- `DOWNSIDE_RISK`

Terminal extension blocks new chase entries. Downside-risk structure also blocks new entries.

### Multi-timeframe aggregation

The engine applies deterministic timeframe weights, with weekly and daily structure carrying more influence than lower higher-timeframe inputs. Relative-strength values are aggregated only when supplied; missing values are not fabricated.

### Broad-market regime

The regime classifier uses BTC structure, BTC extension, market breadth, optional BTC return, and optional market drawdown.

Possible regimes:

- `RISK_ON`
- `SELECTIVE_RISK_ON`
- `NEUTRAL`
- `RISK_OFF`
- `CAPITULATION`
- `RECOVERY`

`RISK_OFF` and `CAPITULATION` block new entries. `NEUTRAL` does not automatically approve new entries.

### Entry eligibility gate

`evaluate_spot_entry_eligibility` blocks strategy evaluation when:

- the market regime does not allow new entries;
- the regime is risk-off or capitulation;
- structure is terminally extended;
- structure shows downside risk;
- the aggregate higher-timeframe trend is bearish.

This is a pre-strategy safety gate. It does not generate a trade setup.

## Configuration

S2 thresholds are stored under `structure` in `config/spot.yaml` and validated through `SpotStructureThresholds`.

Configured values include:

- approved timeframes;
- extension ATR multiple;
- terminal-extension ATR multiple;
- downside-risk ATR multiple;
- zone width ATR multiple;
- risk-on breadth threshold;
- risk-off breadth threshold.

## Tests

Focused tests cover:

- higher-timeframe trend and zone classification;
- terminal-extension detection;
- rejection of `1m` thesis inputs;
- multi-timeframe aggregation;
- risk-on and risk-off regimes;
- terminal-extension entry rejection;
- bearish-structure entry rejection;
- risk-off entry blocking.

## Validation boundary

The GitHub connector cannot run the repository quality gate. S2 must not be declared quality-gate complete until these commands pass locally:

```bash
ruff format .
ruff check .
mypy src
pytest
```

Any failures from this gate must be repaired before starting S3.
