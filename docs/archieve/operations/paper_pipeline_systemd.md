# Paper Pipeline systemd Examples

These examples run Apex's paper-only combined pipelines. They do not place exchange orders.

## Futures service

```ini
[Unit]
Description=Apex futures paper pipeline
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/apex
ExecStart=/opt/apex/.venv/bin/apex paper scheduled-futures-pipeline --symbols-file config/symbols.yaml --mode normal --risk-mode STANDARD --wallet-balance 100 --analysis-candles 200 --lifecycle-timeframe 5m --lifecycle-candles 80 --output json
```

## Futures timer

```ini
[Unit]
Description=Run Apex futures paper pipeline every five minutes

[Timer]
OnCalendar=*:0/5
Persistent=true
RandomizedDelaySec=10
Unit=apex-paper-futures-pipeline.service

[Install]
WantedBy=timers.target
```

## Spot service

```ini
[Unit]
Description=Apex spot paper pipeline
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/apex
ExecStart=/opt/apex/.venv/bin/apex paper scheduled-spot-pipeline --symbols BTC/USDT,ETH/USDT --account config/spot_account.json --analysis-candles 200 --lifecycle-timeframe 5m --lifecycle-candles 80 --output json
```

## Spot timer

```ini
[Unit]
Description=Run Apex spot paper pipeline every fifteen minutes

[Timer]
OnCalendar=*:2/15
Persistent=true
RandomizedDelaySec=10
Unit=apex-paper-spot-pipeline.service

[Install]
WantedBy=timers.target
```

## Operations status service

```ini
[Unit]
Description=Apex paper operations readiness snapshot

[Service]
Type=oneshot
WorkingDirectory=/opt/apex
ExecStart=/opt/apex/.venv/bin/apex paper operations-status --maximum-run-age-minutes 20 --stale-lock-minutes 30 --output json
```

Use separate output capture or journald retention for each service. Do not schedule the standalone intake command concurrently with its combined market pipeline. The market-specific pipeline lock prevents overlapping combined runs, while the lifecycle lock preserves existing cycle-level protection and evidence.
