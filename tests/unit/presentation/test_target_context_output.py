from __future__ import annotations

from apex.presentation.compact_analysis_output import _target_line


def test_target_line_includes_structural_context() -> None:
    target = {
        "price": 101.9,
        "target_timeframe": "3m",
        "rationale": ["front-run of 3m resistance zone 102-102.2"],
    }

    output = _target_line(target, 100.0)

    assert "101.9" in output
    assert "+1.90%" in output
    assert "front-run of 3m resistance zone 102-102.2" in output
