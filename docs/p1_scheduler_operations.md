# P1 Scheduler-Ready Paper Operations

Apex now exposes dedicated overlap-safe commands for continuous paper validation:

```bash
apex paper scheduled-futures --timeframe 5m --candles 80
apex paper scheduled-spot --timeframe 5m --candles 80
```

Each command uses a market-specific lock under `data/paper_trading/scheduler/locks`, skips cleanly when another non-stale cycle is active, replaces stale locks after the configured threshold, and appends a structured JSONL result under `data/paper_trading/scheduler/logs`.

## Cron

Run futures and spot every five minutes, offset by one minute:

```cron
*/5 * * * * cd /home/APEX_USER/data_drive/apex && .venv/bin/apex paper scheduled-futures --timeframe 5m --candles 80 >> data/paper_trading/scheduler/cron-futures.log 2>&1
1-59/5 * * * * cd /home/APEX_USER/data_drive/apex && .venv/bin/apex paper scheduled-spot --timeframe 5m --candles 80 >> data/paper_trading/scheduler/cron-spot.log 2>&1
```

## systemd

Copy the templates from `deploy/systemd`, replace `APEX_USER`, then enable both timers:

```bash
sudo cp deploy/systemd/apex-paper@.service /etc/systemd/system/
sudo cp deploy/systemd/apex-paper@.timer /etc/systemd/system/
sudo sed -i 's/APEX_USER/your-user/g' /etc/systemd/system/apex-paper@.service
sudo systemctl daemon-reload
sudo systemctl enable --now apex-paper@futures.timer
sudo systemctl enable --now apex-paper@spot.timer
systemctl list-timers 'apex-paper@*'
```

Inspect execution and structured application logs with:

```bash
journalctl -u apex-paper@futures.service -n 100 --no-pager
journalctl -u apex-paper@spot.service -n 100 --no-pager
tail -n 20 data/paper_trading/scheduler/logs/futures.jsonl
tail -n 20 data/paper_trading/scheduler/logs/spot.jsonl
```

These services perform paper lifecycle updates only. They do not place exchange orders or authorize production execution.
