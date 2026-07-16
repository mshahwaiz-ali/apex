# Live Spot Orchestration

`apex spot-live` is the public-market-data entrypoint for the long-only cash spot product.

```bash
apex spot-live ETHUSDT \
  --account tests/fixtures/spot_live/account.json \
  --config config/spot.yaml \
  --strategy-config config/spot_strategies.yaml \
  --candles 200 \
  --output data/spot-live.json
```

The command fetches public ticker plus closed `12h` and `4h` candles through the existing provider abstraction. The `12h` series is produced by the configured provider-independent resampling layer from supported `4h` data. It derives measurable EMA, ATR, swing sequence, volume-ratio, and pullback-depth inputs, builds canonical `SpotStructureResult` and `SpotRegimeResult` contracts, and then calls the existing S5 orchestration bridge.

The account file is a strict JSON object containing canonical `SpotAccountInput` under `account` plus optional `current_sector_exposure_percentage`.

Missing candles, insufficient closed history, stale candles, malformed account data, provider errors, and invalid geometry fail explicitly. Optional breakout, retest, accumulation, liquidity-sweep, daily-recovery, and capitulation-recovery confirmations remain unavailable unless a later measurable provider-independent detector supplies them.

Market breadth is not fabricated. Until a breadth scanner is integrated, the live command uses BTC higher-timeframe structure with explicitly unavailable breadth. This can produce selective risk-on, neutral, or risk-off context, but it does not claim broad-market confirmation.

This workflow is research and paper-validation only. It does not place orders or add scanner integration, persistence, paper-trade mutation, optimization, leverage, margin, borrowing, liquidation calculations, short-selling, or production-readiness claims.
