from __future__ import annotations

from dataclasses import MISSING, fields
from inspect import getsource

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.discovery_setup import _build_setup
from apex.domain.methodology_contracts import LayeredStateSnapshot, ScoreDimensions


def test_discovery_setup_methodology_fields_have_safe_defaults() -> None:
    by_name = {field.name: field for field in fields(DiscoverySetup)}

    layered = by_name["layered_state"]
    scores = by_name["methodology_scores"]

    assert layered.default is MISSING
    assert scores.default is MISSING
    assert layered.default_factory() == LayeredStateSnapshot()
    assert scores.default_factory() == ScoreDimensions()


def test_build_setup_projects_candidate_methodology_contracts() -> None:
    source = getsource(_build_setup)

    assert "layered_state=candidate.layered_state" in source
    assert "methodology_scores=candidate.score_dimensions" in source
