"""
Sponsor evaluator, scores potential sponsors across six dimensions

Public surface:
    SponsorEvaluator                    the main entry point (evaluator.py)
    ClaudeSponsorDimensionEvaluator     Anthropic / Claude backed LLM evaluator
    OpenAISponsorDimensionEvaluator     OpenAI / ChatGPT backed LLM evaluator
    GoogleSponsorDimensionEvaluator     Google / Gemini backed LLM evaluator
    SponsorScore                        the evaluation result (schemas.py)
    Company / Evidence                  input data structures (schemas.py)

the orchestrator picks which evaluator to instantiate based on the LLM_PROVIDER
setting
"""

from sponsor_pipeline.services.sponsor_evaluator.evaluator import SponsorEvaluator
from sponsor_pipeline.services.sponsor_evaluator.llm.sponsor_dimension_evaluator import (
    ClaudeSponsorDimensionEvaluator,
    GoogleSponsorDimensionEvaluator,
    OpenAISponsorDimensionEvaluator,
)
from sponsor_pipeline.services.sponsor_evaluator.schemas import (
    Company,
    Evidence,
    SponsorScore,
)

__all__ = [
    "ClaudeSponsorDimensionEvaluator",
    "Company",
    "Evidence",
    "GoogleSponsorDimensionEvaluator",
    "OpenAISponsorDimensionEvaluator",
    "SponsorEvaluator",
    "SponsorScore",
]
