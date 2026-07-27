"""Point-in-time historical campaign and classical-ML support."""

from apex.research.campaign import CampaignConfig, CampaignManifest, PublicDataImporter
from apex.research.edge import EdgePromotionDecision, ExpectedRInputs, evaluate_promotion
from apex.research.evaluation import EvaluationOutcome, evaluate_walk_forward_campaign
from apex.research.experiment import ExperimentManifest
from apex.research.splits import ChronologicalSplit, chronological_split

__all__ = [
    "CampaignConfig",
    "CampaignManifest",
    "ChronologicalSplit",
    "EdgePromotionDecision",
    "EvaluationOutcome",
    "ExpectedRInputs",
    "ExperimentManifest",
    "PublicDataImporter",
    "chronological_split",
    "evaluate_promotion",
    "evaluate_walk_forward_campaign",
]
