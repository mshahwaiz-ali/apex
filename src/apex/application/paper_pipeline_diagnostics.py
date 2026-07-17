"""Stable diagnostic aggregation for futures scans and paper pipelines."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from apex.application.analysis import ScanResult, SymbolAnalysis
from apex.application.candidate_selection_diagnostics import (
    build_candidate_selection_diagnostic_summary,
    candidate_selection_payload,
)
from apex.application.phase6_pipeline_diagnostics import (
    build_phase6_diagnostic_summary,
    phase6_analysis_payload,
)


@dataclass(frozen=True, slots=True)
class Phase4DiagnosticSummary:
    """Deterministic run-level statistics derived from routing diagnostics."""

    rejection_code_counts: Mapping[str, int]
    rejection_counts_by_strategy: Mapping[str, int]
    rejection_counts_by_decision_regime: Mapping[str, int]
    rejection_counts_by_near_miss_state: Mapping[str, int]
    candidate_counts_by_strategy: Mapping[str, int]
    strategies_evaluated: int
    strategies_eligible: int
    strategies_skipped: int
    strategies_producing_candidates: int
    strategies_producing_zero_candidates: int
    htf_breakout_detected: int
    htf_breakout_fallback_eligible: int
    htf_breakout_raw_candidate_produced: int
    htf_breakout_no_candidate: int

    def to_payload(self) -> dict[str, Any]:
        """Serialize counts with deterministic key ordering."""

        return {
            "rejection_code_counts": _sorted_counts(self.rejection_code_counts),
            "rejection_counts_by_strategy": _sorted_counts(
                self.rejection_counts_by_strategy
            ),
            "rejection_counts_by_decision_regime": _sorted_counts(
                self.rejection_counts_by_decision_regime
            ),
            "rejection_counts_by_near_miss_state": _sorted_counts(
                self.rejection_counts_by_near_miss_state
            ),
            "candidate_counts_by_strategy": _sorted_counts(
                self.candidate_counts_by_strategy
            ),
            "strategy_totals": {
                "evaluated": self.strategies_evaluated,
                "eligible": self.strategies_eligible,
                "skipped": self.strategies_skipped,
                "producing_candidates": self.strategies_producing_candidates,
                "producing_zero_candidates": self.strategies_producing_zero_candidates,
            },
            "higher_timeframe_breakout_fallback": {
                "detected": self.htf_breakout_detected,
                "eligible_because_of_fallback": self.htf_breakout_fallback_eligible,
                "raw_candidate_produced": self.htf_breakout_raw_candidate_produced,
                "no_candidate_despite_fallback": self.htf_breakout_no_candidate,
            },
        }


def build_phase4_diagnostic_summary(
    analyses: Sequence[SymbolAnalysis],
) -> Phase4DiagnosticSummary:
    """Aggregate available Phase 4 routing diagnostics without fabricating gaps."""

    rejection_codes: Counter[str] = Counter()
    by_strategy: Counter[str] = Counter()
    by_regime: Counter[str] = Counter()
    by_near_miss: Counter[str] = Counter()
    candidate_counts: Counter[str] = Counter()
    evaluated = eligible = skipped = producing = zero = 0
    htf_detected = htf_fallback_eligible = htf_candidate = htf_no_candidate = 0

    for analysis in analyses:
        routing = analysis.strategy_routing or {}
        diagnostics = _mapping(routing.get("phase4_strategy_diagnostics"))
        routed_eligible = set(_strings(routing.get("routed_eligible_strategies")))
        skipped_strategies = _mapping(routing.get("skipped_strategies"))
        regime = _optional_string(routing.get("decision_regime"))
        htf_breakout = routing.get("higher_timeframe_breakout") is True

        evaluated += len(diagnostics)
        eligible += len(routed_eligible)
        skipped += len(skipped_strategies)
        if htf_breakout:
            htf_detected += 1

        fallback_strategies: set[str] = set()
        for strategy, raw_diagnostic in diagnostics.items():
            diagnostic = _mapping(raw_diagnostic)
            count = _non_negative_int(diagnostic.get("candidate_count"))
            candidate_counts[strategy] += count
            if count > 0:
                producing += 1
            else:
                zero += 1

            near_miss = _optional_string(diagnostic.get("near_miss_state"))
            codes = _strings(diagnostic.get("rejection_codes"))
            for code in codes:
                rejection_codes[code] += 1
                by_strategy[strategy] += 1
                if regime is not None:
                    by_regime[regime] += 1
                if near_miss is not None:
                    by_near_miss[near_miss] += 1

            if (
                htf_breakout
                and strategy in routed_eligible
                and strategy in {"breakout_continuation", "momentum_continuation"}
            ):
                fallback_strategies.add(strategy)
                if count > 0:
                    htf_candidate += 1
                else:
                    htf_no_candidate += 1
        htf_fallback_eligible += len(fallback_strategies)

    return Phase4DiagnosticSummary(
        rejection_code_counts=rejection_codes,
        rejection_counts_by_strategy=by_strategy,
        rejection_counts_by_decision_regime=by_regime,
        rejection_counts_by_near_miss_state=by_near_miss,
        candidate_counts_by_strategy=candidate_counts,
        strategies_evaluated=evaluated,
        strategies_eligible=eligible,
        strategies_skipped=skipped,
        strategies_producing_candidates=producing,
        strategies_producing_zero_candidates=zero,
        htf_breakout_detected=htf_detected,
        htf_breakout_fallback_eligible=htf_fallback_eligible,
        htf_breakout_raw_candidate_produced=htf_candidate,
        htf_breakout_no_candidate=htf_no_candidate,
    )


def build_futures_pipeline_diagnostics(scan: ScanResult) -> dict[str, Any]:
    """Return detailed and run-level Phase 4 through Phase 6 diagnostics."""

    phase4_analyses = {
        _analysis_key(analysis): _analysis_diagnostics(analysis)
        for analysis in scan.analyses
    }
    phase5_analyses = {
        _analysis_key(analysis): candidate_selection_payload(analysis)
        for analysis in scan.analyses
    }
    phase6_source = tuple(
        analysis for analysis in scan.analyses if hasattr(analysis, "assessment")
    )
    phase6_analyses = {
        _analysis_key(analysis): phase6_analysis_payload(analysis)
        for analysis in phase6_source
    }
    return {
        "scan_analysis_count": len(scan.analyses),
        "scanner_failure_count": len(scan.failures),
        "scanner_failures": dict(sorted(scan.failures.items())),
        "phase4_summary": build_phase4_diagnostic_summary(scan.analyses).to_payload(),
        "phase4_analyses": phase4_analyses,
        "phase5_summary": build_candidate_selection_diagnostic_summary(scan.analyses).to_payload(),
        "phase5_analyses": phase5_analyses,
        "phase6_summary": build_phase6_diagnostic_summary(phase6_source).to_payload(),
        "phase6_analyses": phase6_analyses,
    }


def _analysis_key(analysis: SymbolAnalysis) -> str:
    return analysis.symbol


def _analysis_diagnostics(analysis: SymbolAnalysis) -> dict[str, Any]:
    routing = analysis.strategy_routing or {}
    return {
        "symbol": analysis.symbol,
        "candidate_count": analysis.candidate_count,
        "decision_regime": routing.get("decision_regime"),
        "higher_timeframe_breakout": routing.get("higher_timeframe_breakout") is True,
        "near_miss_state_counts": dict(
            sorted(_mapping(routing.get("near_miss_state_counts")).items())
        ),
        "phase4_strategy_diagnostics": dict(
            sorted(_mapping(routing.get("phase4_strategy_diagnostics")).items())
        ),
        "routed_eligible_strategies": sorted(
            _strings(routing.get("routed_eligible_strategies"))
        ),
        "skipped_strategies": dict(
            sorted(_mapping(routing.get("skipped_strategies")).items())
        ),
    }


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(str(item) for item in value)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _non_negative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _sorted_counts(values: Mapping[str, int]) -> dict[str, int]:
    return {key: values[key] for key in sorted(values)}
