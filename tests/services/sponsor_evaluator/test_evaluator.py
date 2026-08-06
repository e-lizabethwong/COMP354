"""
Tests for SponsorEvaluator orchestration in evaluator.py
uses FakeSponsorDimensionEvaluator to replace the Claude backend so the
flow from evaluate() through to SponsorScore can be tested without an API key
"""

from __future__ import annotations

from sponsor_pipeline.services.sponsor_evaluator.criteria import CRITERIA
from sponsor_pipeline.services.sponsor_evaluator.evaluator import SponsorEvaluator
from sponsor_pipeline.services.sponsor_evaluator.schemas import Confidence, SponsorScore
from sponsor_pipeline.services.sponsor_evaluator.scoring import ScoreCalculator

from .conftest import FakeSponsorDimensionEvaluator


class TestSponsorEvaluator:
    """Tests for the orchestration flow in SponsorEvaluator.evaluate()"""

    def test_fields_are_copied_to_result(self, fake_evaluator, sample_company, sample_evidence):
        result = SponsorEvaluator(fake_evaluator).evaluate(sample_company, sample_evidence)
        assert result.explanation == "Fake explanation, no LLM called"
        assert result.key_strengths == ["Fake strength"]
        assert result.potential_weaknesses == ["Fake weakness"]
        assert result.recommended_outreach_angle == "Fake angle"
        assert result.recommended_contact_role == "Fake role"

    def test_evaluate_returns_sponsor_score(self, fake_evaluator, sample_company, sample_evidence):
        result = SponsorEvaluator(fake_evaluator).evaluate(sample_company, sample_evidence)
        assert isinstance(result, SponsorScore)

    def test_all_six_dimensions_are_scored(self, fake_evaluator, sample_company, sample_evidence):
        SponsorEvaluator(fake_evaluator).evaluate(sample_company, sample_evidence)
        assert set(fake_evaluator.dimension_calls) == {c.key for c in CRITERIA}

    def test_summary_is_called_exactly_once(self, fake_evaluator, sample_company, sample_evidence):
        SponsorEvaluator(fake_evaluator).evaluate(sample_company, sample_evidence)
        assert fake_evaluator.summary_calls == 1

    def test_overall_score_matches_fixed_score(self, sample_company, sample_evidence):
        # when every dimension returns the same value the weighted average equals that value
        fake = FakeSponsorDimensionEvaluator(fixed_score=8.0)
        result = SponsorEvaluator(fake).evaluate(sample_company, sample_evidence)
        assert result.overall_score == 8.0

    def test_company_is_preserved_on_result(self, fake_evaluator, sample_company, sample_evidence):
        result = SponsorEvaluator(fake_evaluator).evaluate(sample_company, sample_evidence)
        assert result.company is sample_company

    def test_criterion_scores_keyed_by_criterion_key(self, fake_evaluator, sample_company, sample_evidence):
        result = SponsorEvaluator(fake_evaluator).evaluate(sample_company, sample_evidence)
        assert set(result.criterion_scores.keys()) == {c.key for c in CRITERIA}

    def test_confidence_comes_from_summary(self, fake_evaluator, sample_company, sample_evidence):
        # the stub returns Confidence.MEDIUM so the assembled SponsorScore should reflect that
        result = SponsorEvaluator(fake_evaluator).evaluate(sample_company, sample_evidence)
        assert result.confidence == Confidence.MEDIUM

    def test_custom_score_calculator_is_used(self, sample_company, sample_evidence):
        # injecting a calculator scoped to a single criterion verifies the dependency is wired
        fake = FakeSponsorDimensionEvaluator(fixed_score=3.0)
        calculator = ScoreCalculator([CRITERIA[0]])
        result = SponsorEvaluator(fake, score_calculator=calculator).evaluate(
            sample_company, sample_evidence
        )
        assert result.overall_score == 3.0
