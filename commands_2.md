# Apex Command Guide

Apex exposes a focused trade-discovery CLI. It finds and explains Binance USDT
perpetual-futures setups; it does not place orders or manage accounts.

## Commands

| Command | Purpose |
|---|---|
| `apex scan` | Discover, analyze, and rank active futures opportunities. |
| `apex analyze SYMBOL` | Run the same full analysis pipeline for one requested symbol. |
| `apex backtest SYMBOL` | Replay focused trade-discovery analysis against historical market data. |
| `apex config-check` | Validate configuration files and print resolved settings. |
| `apex version` | Show the installed Apex version. |

## Common Usage

```bash
apex scan
apex scan --results 10 --shortlist 40 --direction both
apex scan --output json --report reports/latest_scan.json
apex analyze BTCUSDT
apex analyze BTCUSDT --output json
apex backtest BTCUSDT
apex config-check
```

## Output Modes

`scan` and `analyze` support:

| Mode | Use |
|---|---|
| `--output text` | Operator-facing summary with decision group, entry geometry, targets, warnings, and methodology notes. |
| `--output json` | Stable structured payload for records, reports, and downstream tooling. |

Text output now highlights:

- decision group first: actionable, developing, unavailable, or no trade;
- why the symbol entered discovery lanes;
- why the selected direction and entry were chosen;
- stop, invalidation, and target interpretation;
- contextual candlestick evidence when present.

## Methodology Notes

- `apex scan` and `apex analyze SYMBOL` share the same full-analysis core after symbol selection.
- Discovery lane tags explain shortlist routing only; they do not approve trades.
- Candlestick patterns are timing and confirmation evidence only. They do not create targets, bypass structure, or override missing stop and target geometry.
- `READY_NOW` means rule-defined execution conditions are complete. It does not mean the next trade outcome is certain.
- Confidence labels describe evidence quality or calibrated history only when calibration metadata is available; uncalibrated percentages are not shown as win probability.
