"""Deterministically select one canonical entry opportunity when execution state permits."""

from __future__ import annotations

from apex.application.methodology_contracts import EntryOpportunity, EntryOpportunityType
from apex.application.methodology_selected_entry_contracts import SelectedEntryDecision
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.methodology_strategy_contracts import SetupMaturity


_BLOCKED_MATUR