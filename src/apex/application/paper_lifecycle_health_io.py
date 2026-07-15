"""Load and persist deterministic lifecycle health evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from apex.application.paper_lifecycle_analytics import (
    PaperLifecycleAnalytics,
    PaperLifecycleTradeRecord,
)
from apex.application.paper_lifecycle_health import (
    PaperLifecycleHealthPolicy,
    PaperLifecycleHealthReport,
    evaluate_p