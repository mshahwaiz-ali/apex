"""Install corrected CLI commands."""

from __future__ import annotations

import typer

from apex.cli_commands.analysis import register_analysis_commands
from apex.cli_commands.backtest_campaign_risk_mode import register_risk_mode_campaign_command
from apex.cli_commands.backtesting import register_backtesting_commands
from apex.cli_commands.daily_validation import register_daily_validation_commands
from apex.cli_commands.datasets import register_dataset_commands
from apex.cli_commands.evidence_bundle import register_evidence_bundle_commands
from apex.cli_commands.evidence_pipeline import register_evidence_pipeline_commands
from apex.cli_commands.forward_edge import register_forward_edge_commands
from apex.cli_commands.funded_history import register_funded_history_commands
from apex.cli_commands.historical_futures_edge import register_historical_futures_edge_commands
from apex.cli_commands.historical_futures_edge_validation import (
    register_historical_futures_edge_validation_commands,
)
from apex.cli_commands.history_review import register_history_review_commands
from apex.cli_commands.market_data import register_market_data_commands
from apex.cli_commands.paper_record_v3 import register_paper_record_v3
from apex.cli_commands.paper_trading import register_paper_trading_commands
from apex.cli_commands.readiness import register_readiness_commands
from apex.cli_commands.scanner import register_scanner_commands
from apex.cli_commands.spot_analysis import register_spot_analysis_commands
from apex.cli_commands.spot_live import register_spot_live_commands
from apex.cli_commands.spot_live_scanner import register_spot_live_scanner_commands
from apex.cli_commands.spot_orchestration import register_spot_orchestration_commands
from apex.cli_commands.spot_planning import register_spot_planning_commands
from apex.cli_commands.validation_evidence import register_validation_evidence_commands
from apex.cli_commands.validation_pipeline import register_validation_pipeline_commands
from apex.cli_overlay import remove_commands


def install_cli_commands(app: typer.Typer, paper_app: typer.Typer) -> None:
    remove_commands(app, {"fetch", "ticker", "analyze", "scan", "backtest"})
    remove_commands(paper_app, {"record", "update", "report", "replay-report"})
    register_market_data_commands(app)
    register_analysis_commands(app)
    register_scanner_commands(app)
    register_dataset_commands(app)
    register_backtesting_commands(app)
    register_historical_futures_edge_commands(app)
    register_historical_futures_edge_validation_commands(app)
    register_forward_edge_commands(app)
    register_evidence_bundle_commands(app)
    register_evidence_pipeline_commands(app)
    register_spot_analysis_commands(app)
    register_spot_orchestration_commands(app)
    register_spot_live_commands(app)
    register_spot_live_scanner_commands(app)
    register_spot_planning_commands(app)
    remove_commands(app, {"chronological-backtest-campaign"})
    register_risk_mode_campaign_command(app)
    register_readiness_commands(app)
    register_validation_evidence_commands(app)
    register_validation_pipeline_commands(app)
    register_daily_validation_commands(app)
    register_history_review_commands(app)
    register_funded_history_commands(app)
    register_paper_trading_commands(paper_app)
    remove_commands(paper_app, {"record"})
    register_paper_record_v3(paper_app)
