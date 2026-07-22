from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_module() -> ModuleType:
    path = Path("tools/run_anchored_backtest_campaign.py")
    spec = importlib.util.spec_from_file_location("run_anchored_backtest_campaign", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_runner_accepts_current_backtest_schema(monkeypatch: Any, tmp_path: Path) -> None:
    module = _load_module()
    report = tmp_path / "report.json"
    log = tmp_path / "report.log"
    job = module.CampaignJob(
        symbol="BTCUSDT",
        profile=module.PROFILES[0],
        anchor=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        report_path=report,
        log_path=log,
    )

    class Completed:
        returncode = 0

    def fake_run(*args: object, **kwargs: object) -> Completed:
        del args, kwargs
        report.write_text(
            json.dumps({"schema_version": module.EXPECTED_BACKTEST_SCHEMA_VERSION}),
            encoding="utf-8",
        )
        return Completed()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.run_job(job, apex_command="apex", candle_limit=240)

    assert result.succeeded is True
    assert result.report_valid is True
    assert result.error is None


def test_runner_reports_actual_schema_on_mismatch(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    module = _load_module()
    report = tmp_path / "report.json"
    log = tmp_path / "report.log"
    job = module.CampaignJob(
        symbol="BTCUSDT",
        profile=module.PROFILES[0],
        anchor=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        report_path=report,
        log_path=log,
    )

    class Completed:
        returncode = 0

    def fake_run(*args: object, **kwargs: object) -> Completed:
        del args, kwargs
        report.write_text(json.dumps({"schema_version": 4}), encoding="utf-8")
        return Completed()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.run_job(job, apex_command="apex", candle_limit=240)

    assert result.succeeded is False
    assert result.report_valid is False
    assert result.error == "report schema is missing or unexpected: expected 5, got 4"
