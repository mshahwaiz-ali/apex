# Phase B Timeframe Resampling

Source of truth: `docs/plan_2.md`.

This note records the first deterministic higher-timeframe resampling implementation.

## Behavior

* Native provider timeframes are fetched unchanged.
* Configured non-native timeframes are resampled through `ResamplingMarketDataProvider`.
* Resampling sources are controlled by `timeframe_resampling_sources` in `config/default.yaml`.
* OHLCV aggregation uses:
  * open from the first source candle
  * high as the maximum high
  * low as the minimum low
  * close from the last source candle
  * volume as the sum of source volumes
* Resampled candles use `source=resampled:<source_timeframe>:<provider>`.
* The final incomplete target bucket is retained and marked `is_closed=false`.
* A leading partial bucket is skipped.
* Gaps, duplicate or unordered source candles, multiple active source candles, and mid-series incomplete target buckets are rejected.

## Defaults

Default resampling sources:

```text
1W  <- 4h
3D  <- 4h
1D  <- 4h
12h <- 4h
8h  <- 4h
6h  <- 1h
2h  <- 1h
```

These defaults preserve the current native lower-timeframe provider boundary while allowing optional higher contextual frames to be enabled through configuration.

## Limitations

* Resampling is deterministic and local; it does not prove provider support for native higher timeframes.
* Very high target limits can be bounded by the provider source limit, so fewer target candles may be returned.
* Live ticker, mark, and index prices remain separate future inputs.

## Price and Freshness Metadata

Each `TimeframeContext` now exposes explicit price and data-quality fields:

```text
latest_closed_price
active_candle_price
ticker_price
mark_price
index_price
analysis_price
last_closed_at
last_received_at
staleness_seconds
is_stale
data_confidence
```

Current strategy behavior remains backward-compatible:

* `current_price` uses ticker price when available, then active-candle price, then latest closed price.
* `analysis_price` is the latest closed candle close.
* `active_candle_price` is populated only when the final candle is active.
* ticker, mark, and index prices are explicit nullable fields until dedicated live-price wiring is added.
* `current_price_source` records which price source was selected.

Staleness thresholds are configured through `timeframe_max_staleness_seconds` in `config/default.yaml`.
Serialized symbol-analysis output exposes these fields under `timeframe_data_quality`.

Additional candle validation now rejects:

* timezone-naive validation clocks
* timezone-naive candle timestamps
* candles that open in the future
* closed candles whose close time is still in the future
* active candles whose close time has already passed
