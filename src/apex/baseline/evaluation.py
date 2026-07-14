"""Deterministic evaluation of frozen baseline campaign scenarios."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence

from apex.application.baseline_campaign_plan import BaselineCampaignPlan
from apex.backtesting import HistoricalEdgeProfile
from apex.baseline.contracts import (
    BaselineEvaluationPolicy,
    BaselineEvaluationReport,
    BaselineReason,
    BaselineScenario,
    BaselineVerdict,
    CostSensitivityResult,
    StrategyBaselineAssessment,
)


def evaluate_baseline_campaigns(
    plan: BaselineCampaignPlan,
    scenarios: Sequence[BaselineScenario],
    *,
    baseline_scenario_id: