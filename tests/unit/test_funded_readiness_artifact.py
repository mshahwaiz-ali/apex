from __future__ import annotations

import json
from pathlib import Path

import pytest

from apex.funded.readiness_artifact import (
    build_funded_readiness_artifact,
    load_and_verify_funded_readiness_artifact,
    write_funded_readiness_artifact,
)


def _write_input(path: Path, *, provider: str = "Example Funded") -> None:
    path.write_text(
        json.dumps({"provider_limits": {"provider_name": provider}}, sort_keys=True) + "\n