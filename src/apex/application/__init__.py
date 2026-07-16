"""Stable public API used by the Apex command-line layer.

Keep this facade intentionally small. Importing optional application subsystems here can
create cycles because lower-level backtesting and paper-trading modules import focused
application modules directly.
"""

from apex.application.account_state import AccountStateSnapshot, AccountStateStore
from apex.application.analysis_records import (
    build_analysis_record,
