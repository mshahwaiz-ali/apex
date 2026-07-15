"""Load deterministic lifecycle health evidence from paper pipeline audits."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any

from apex.application.paper_lifecycle_analytics import (
    PaperLifecycleAnalytics,
    PaperLifecycleTradeRecord,
)
from apex.application.paper_lifecycle_health import (
    PaperLifecycleHealthPolicy,
    PaperLifecycleHealthReport,
    evaluate_p