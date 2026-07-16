from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

from apex.application.paper_lifecycle_analytics import PaperLifecycleAnalytics
from apex.application.paper_lifecycle_health import PaperLifecycleHealthPolicy
from apex.application.paper_lifecycle_health_io import (
    build_paper_lifecycle_health_artifact,
    load_latest_paper_lifecycle_health,
    write_paper_lifecycle_health_artifact,
)
from apex.application.paper_lifecycle_health_verification import (
    PaperLifecycleHealthSourceStatus,
    paper_lifecycle_health_source_verification_payload,
    verify_paper_lifecycle_health_artifact_source,