"""
Shared fixtures for sponsor_evaluator tests

FakeSponsorDimensionEvaluator is a concrete stub of the abstract
SponsorDimensionEvaluator that returns deterministic results without any
API calls, so the orchestration and pure-Python parts of the module can be
tested without an API key

change what the fake returns ---> adjust fixed_score or override in the test
"""

from __future__ import annotations

import pytest

from sponsor_pipeline.services.sponsor_evaluator.criteria import EvaluationCriterion
from sponsor_pipeline.services.sponsor_evaluator.llm.sponsor_dimension_evaluator import (
    SponsorDimensionEvaluator,
    SponsorEvaluationSummary,
)
from sponsor_pipeline.services.sponsor_evaluator.schemas import (
    Company,
    Confidence,
    CriterionScore,
    Evidence,
    SponsorMotivation,
)


# ---------------------------------------------------------------------------
# Stub implementation, satisfies the abstract contract without hitting an API
# ---------------------------------------------------------------------------


class FakeSponsorDimensionEvaluator(SponsorDimensionEvaluator):
    """
    Deterministic stub of SponsorDimensionEvaluator for use in tests
    returns fixed_score(default 5.0) for every dimension and a canned summary
    also records which dimension keys were requested and how many times
    evaluate_summary was called, so tests can assert on call behaviour
    """

    def __init__(self, fixed_score: float = 5.0) -> None:
        self.fixed_score = fixed_score
        self.dimension_calls: list[str] = []
        self.summary_calls: int = 0

    def evaluate_dimension(
        self,
        criterion: EvaluationCriterion,
        company: Company,
        evidence: Evidence,
    ) -> CriterionScore:
        self.dimension_calls.append(criterion.key)
        return CriterionScore(
            criterion_key=criterion.key,
            score=self.fixed_score,
            reasoning="Fake reasoning, no LLM called",
            supporting_evidence=[],
        )

    def evaluate_summary(
        self,
        company: Company,
        evidence: Evidence,
        criterion_scores: dict[str, CriterionScore],
    ) -> SponsorEvaluationSummary:
        self.summary_calls += 1
        return SponsorEvaluationSummary(
            motivations=[SponsorMotivation.TALENT],
            confidence=Confidence.MEDIUM,
            explanation="Fake explanation, no LLM called",
            key_strengths=["Fake strength"],
            potential_weaknesses=["Fake weakness"],
            recommended_outreach_angle="Fake angle",
            recommended_contact_role="Fake role",
        )


# ---------------------------------------------------------------------------
# Shared pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_evaluator() -> FakeSponsorDimensionEvaluator:
    return FakeSponsorDimensionEvaluator()


@pytest.fixture
def sample_company() -> Company:
    return Company(name="Acme Corp", website="https://acme.example.com", industry="Tech")


@pytest.fixture
def sample_evidence() -> Evidence:
    return Evidence(
        hiring_signals=["Hiring software interns in Waterloo"],
        developer_products=["Public REST API with free tier"],
        past_sponsorships=["Gold sponsor at HackTheNorth 2024"],
        contact_signals=["partnerships@acme.example.com listed on site"],
        company_size_signals=["Series B, ~200 employees"],
        canada_signals=["Toronto office"],
    )
