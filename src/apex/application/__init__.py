"""Stable public API used by the Apex command-line layer.

Keep this facade intentionally small. Importing optional application subsystems here can
create cycles because lower-level backtesting and paper-trading modules import focused
application modules directly.
"""

from apex.application.account_state import AccountStateSnapshot, AccountStateStore
from apex.application.analysis_records import (
    build_analysis_record,
    list_analysis_record_metadata_sqlite,
    load_analysis_record_sqlite,
    write_analysis_record,
    write_analysis_record_sqlite,
)
from apex.application.backtest_campaign import (
    BacktestCampaignRequest,
    MultiSymbolBacktestCampaignRequest,
    campaign_result_to_payload,
    parse_campaign_variants