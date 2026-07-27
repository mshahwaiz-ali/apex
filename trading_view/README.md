# Apex TradingView Companion

`apex_script.pine` is a lightweight TradingView companion for selected Apex concepts.
It is **not** the canonical Python Apex analysis engine and it must not be presented as
producing identical decisions to `apex scan` or `apex analyze`.

## Current scope

The script provides:

- Pine Script v6 indicator mode;
- role-aware local EMA, RSI, ATR, and relative-volume profiles;
- strict previous-confirmed higher-timeframe setup and macro context;
- trend, range, compression, expansion, failed-breakout, and chaotic regimes;
- independent long and short candidate evaluation;
- four initial setup families:
  - trend pullback;
  - breakout or breakdown retest;
  - failed breakout or failed breakdown reclaim;
  - range-edge rejection;
- deterministic long-versus-short arbitration;
- entry range, ideal entry, maximum chase, stop, TP1, TP2, and conditional TP3;
- one compact dashboard and one active geometry display;
- closed-candle ready alerts.

## Important limitations

TradingView cannot reproduce the complete Apex authority, including:

- Binance-wide market discovery;
- full point-in-time derivatives evidence;
- exchange metadata and account-specific execution costs;
- cross-sectional market profiling;
- persistent research and outcome databases;
- canonical opportunity-portfolio arbitration;
- the Python chronological replay engine.

The displayed quality value is a rule-based evidence score, not a calibrated win
probability. No signal guarantees profitability.

## Installation

1. Open TradingView and a chart.
2. Open **Pine Editor**.
3. Replace the editor contents with `apex_script.pine`.
4. Save the script and select **Add to chart**.
5. Start with `Auto`, `Balanced`, and closed-candle signals enabled.

## Initial validation matrix

Test at minimum:

- BTCUSDT and ETHUSDT;
- one strongly trending altcoin;
- one range-bound symbol;
- 1m, 5m, 15m, 1h, and 4h charts.

Confirm that:

- Pine compiles without errors;
- setup and macro values remain stable during the active chart candle;
- ready alerts fire only on a new confirmed ready state;
- stop and target levels remain on the correct side of entry;
- chased entries are not labelled ready;
- TP3 is disabled under meaningful higher-timeframe conflict.

## Updating only this folder locally

The following commands fetch remote `main` and replace only the local
`trading_view/` folder. Other working-tree files are not changed.

```bash
cd ~/data_drive/apex
git fetch origin main
git restore --source=origin/main --staged --worktree -- trading_view
```

This intentionally overwrites any uncommitted local changes inside
`trading_view/`, while leaving Codex work elsewhere in the repository untouched.
