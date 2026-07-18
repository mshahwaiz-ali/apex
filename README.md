# Apex Trading Agent

<p align="center">
  <strong>Deterministic Binance USDT perpetual-futures discovery, setup analysis, and chronological replay.</strong>
</p>

<p align="center">
  <code>Python 3.11+</code> · <code>Typer</code> · <code>Pydantic v2</code> · <code>YAML</code> · <code>Ruff</code> · <code>mypy</code> · <code>pytest</code>
</p>

---

Apex scans Binance USDT perpetual-futures markets, shortlists symbols with usable opportunity characteristics, runs a shared multi-timeframe analysis engine, generates strategy candidates, evaluates entry/stop/target geometry, and explains why a setup is actionable, developing, late, invalid, or unavailable.

Apex is designed to answer five practical questions:

1. **Which markets are worth deeper analysis right now?**