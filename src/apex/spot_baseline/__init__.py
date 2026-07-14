"""Public V2 spot baseline campaign API."""

from apex.spot_baseline.contracts import (
    SpotAllocationVariant,
    SpotBaselineCampaignPlan,
    SpotBaselineEvaluationPolicy,
    SpotBaselineReason,
    SpotBaselineReport,
    SpotBaselineVerdict,
    SpotCampaignCell,
    SpotCampaignResult,
    SpotCostSensitivity,
    SpotCostVariant,
    SpotDatasetReference,
    SpotDatasetRole,
    SpotStrategyAssessment,
)
from apex.spot_baseline.evaluation import (
    evaluate_spot_baseline_campaigns,
    spot_baseline_report_to_payload,
)
from apex.spot_baseline.execution import (
    SpotCampaignInput,
    execute_spot_baseline_plan,
)
from apex.spot_baseline.json_io import (
    SPOT_BASELINE_REPORT_SCHEMA_VERSION,
    load_spot_baseline_report_payload,
    write_spot_baseline_report,
)
from apex.spot_baseline.planning import build_spot_baseline_plan
from apex.spot_baseline.sqlite_io import (
    SPOT_BASELINE_REPORT_DB_SCHEMA_VERSION,
    list_spot_baseline_report_metadata_sqlite,
    load_spot_baseline_report_sqlite,
    write_spot_baseline_report_sqlite,
)

__all__ = [
    "SPOT_BASELINE_REPORT_DB_SCHEMA_VERSION",
    "SPOT_BASELINE_REPORT_SCHEMA_VERSION",
    "SpotAllocationVariant",
    "SpotBaselineCampaignPlan",
    "SpotBaselineEvaluationPolicy",
    "SpotBaselineReason",
    "SpotBaselineReport",
    "SpotBaselineVerdict",
    "SpotCampaignCell",
    "SpotCampaignInput",
    "SpotCampaignResult",
    "SpotCostSensitivity",
    "SpotCostVariant",
    "SpotDatasetReference",
    "SpotDatasetRole",
    "SpotStrategyAssessment",
    "build_spot_baseline_plan",
    "evaluate_spot_baseline_campaigns",
    "execute_spot_baseline_plan",
    "list_spot_baseline_report_metadata_sqlite",
    "load_spot_baseline_report_payload",
    "load_spot_baseline_report_sqlite",
    "spot_baseline_report_to_payload",
    "write_spot_baseline_report",
    "write_spot_baseline_report_sqlite",
]
