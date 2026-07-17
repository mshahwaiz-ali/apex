"""Focused public application API for Apex trade discovery.

Only services required by the active CLI surface are re-exported here. Legacy
account, execution, paper-trading, campaign, funded-readiness, and spot modules
remain internal until they are removed or redesigned.
"""

from apex.application.analysis_records import (
    build_analysis_record,
    write_analysis_record,
    write_analysis_record_sqlite,
)
from apex.application.bootstrap import bootstrap
from apex.application.decision_analysis import (
    ScanResult