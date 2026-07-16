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
from apex.cli_commands.funded_plan_generation import register_funded_plan_generation_commands
from apex.cli_commands.funded_plan_reporting import register_funded_plan_reporting_commands
from apex.cli_commands.historical_futures_edge import register_historical_futures_edge_commands
from apex.cli_commands.historical_futures_edge_validation import (
    register_historical_futures_edge_validation_commands,
)
from apex.cli_commands.history_review import register_history_review_commands
from apex.cli_commands.market_data import register_market_data_commands
from apex.cli_commands.p1_review import register_p1_review_command
from apex.cli_commands.paper_cycle import register_paper_cycle_command
from apex.cli_commands.paper_daily import register_paper_daily_command
from apex.cli_commands.paper_evidence_progress import register_paper_evidence_progress_command
from apex.cli_commands.paper_intake import register_paper_intake_commands
from apex.cli_commands.paper_pipeline import register_paper_pipeline_commands
from apex.cli_commands.paper_record_v3 import register_paper_record_v3
from apex.cli_commands.paper_scheduler import register_paper_scheduler_commands
from apex.cli_commands.paper_status import register_paper_status_command
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
    register_funded_plan_generation_commands(app)
    register_funded_plan_reporting_commands(app)
    register_paper_trading_commands(paper_app)
    register_paper_cycle_command(paper_app)
    register_paper_scheduler_commands(paper_app)
    register_paper_pipeline_commands(paper_app)
    register_paper_status_command(paper_app)
    register_paper_daily_command(paper_app)
    register_paper_evidence_progress_command(paper_app)
    register_paper_intake_commands(paper_app)
    register_p1_review_command(paper_app)
    remove_commands(paper_app, {"record"})
    register_paper_record_v3(paper_app)
