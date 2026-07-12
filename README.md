# Apex Trading Agent

Apex is a deterministic, Python-based crypto market analysis and paper-trading engine. The project prioritizes explainable multi-timeframe analysis, structured risk, reproducible testing, and near-market actionable setups.

The authoritative roadmap is [`plan.md`](plan.md).

## Current status

Phase 0 repository foundation:

- Installable `src/apex` package
- Validated YAML and environment configuration
- Central logging bootstrap
- Provider-independent core domain models
- Typer CLI
- Unit and integration smoke tests
- Ruff, mypy, pytest, and GitHub Actions CI

No strategy or real-order execution logic is included yet.

## Requirements

- Python 3.11+
- Ubuntu/Linux, macOS, or Windows

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Commands

```bash
apex version
apex validate-config
apex smoke
```

## Quality checks

```bash
ruff check .
ruff format --check .
mypy src
pytest --cov=apex --cov-report=term-missing
```

## Safety boundary

Apex currently performs no real-money order execution. Any future execution module must remain isolated and pass the validation gates defined in `plan.md`.
