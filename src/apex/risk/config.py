"""Validated configuration for the deterministic Phase 6 risk engine.

``RiskConfig`` remains the compatibility contract consumed by the existing
Phase-6 setup engine. Runtime account and futures limits are resolved from the
canonical futures risk-mode and account-policy configuration files instead of
being duplicated in ``config/risk.yaml``.
"""

from __future__ import annotations

import