"""
Tests for ScoreCalculator in scoring.py
covers the weighted average math, normalisation, edge cases, and the
validation guard rails — no API key required
"""

from __future__ import annotations

import pytest

from sponsor_pipeline.services.sponsor_evaluator.criteria import (
    CRITERIA,
    EvaluationCriterion,
)
from sponsor_pipeline.services.sponsor_evaluator.schemas import CriterionScore
from sponsor_pipeline.services.sponsor_evaluator.scoring import ScoreCalculator

# ---------------------------------------------------------------------------
# Helpers, build minimal objects without touching the LLM layer
# ---------------------------------------------------------------------------


def _criterion(key: str, weight: float) -> EvaluationCriterion:
    return EvaluationCriterion(key=key, name=key, description="", weight=weight)


def _score(key: str, value: float) -> CriterionScore:
    return CriterionScore(criterion_key=key, score=value, reasoning="", supporting_evidence=[])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScoreCalculator:
    """Tests for the weighted average math and validation in ScoreCalculator"""

    def test_equal_weights(self):
        # both weights are 1.0, so the result is just the arithmetic mean
        criteria = [_criterion("a", 1.0), _criterion("b", 1.0)]
        scores = {"a": _score("a", 4.0), "b": _score("b", 6.0)}
        assert ScoreCalculator(criteria).compute(scores) == 5.0

    def test_higher_weight_pulls_result(self):
        # criterion "a" has 3x the weight so it dominates the average
        criteria = [_criterion("a", 3.0), _criterion("b", 1.0)]
        scores = {"a": _score("a", 10.0), "b": _score("b", 0.0)}
        assert ScoreCalculator(criteria).compute(scores) == 7.5

    def test_single_criterion(self):
        criteria = [_criterion("only", 2.0)]
        scores = {"only": _score("only", 8.0)}
        assert ScoreCalculator(criteria).compute(scores) == 8.0

    def test_ignores_scores_not_in_criteria(self):
        # extra keys in the scores dict that have no matching criterion are silently ignored
        criteria = [_criterion("a", 1.0)]
        scores = {"a": _score("a", 6.0), "z": _score("z", 0.0)}
        assert ScoreCalculator(criteria).compute(scores) == 6.0

    def test_result_is_rounded_to_two_decimal_places(self):
        criteria = [_criterion("a", 1.0), _criterion("b", 1.0), _criterion("c", 1.0)]
        scores = {
            "a": _score("a", 1.0),
            "b": _score("b", 2.0),
            "c": _score("c", 3.0),
        }
        result = ScoreCalculator(criteria).compute(scores)
        assert result == round(result, 2)

    def test_real_criteria_uniform_score(self):
        # if every dimension scores the same value, the weighted average equals that value
        scores = {c.key: _score(c.key, 7.0) for c in CRITERIA}
        assert ScoreCalculator(CRITERIA).compute(scores) == 7.0

    def test_score_exactly_zero_is_valid(self):
        criteria = [_criterion("a", 1.0)]
        scores = {"a": _score("a", 0.0)}
        assert ScoreCalculator(criteria).compute(scores) == 0.0

    def test_score_exactly_ten_is_valid(self):
        criteria = [_criterion("a", 1.0)]
        scores = {"a": _score("a", 10.0)}
        assert ScoreCalculator(criteria).compute(scores) == 10.0

    # ------------------------------------------------------------------
    # Validation, guard rails that must raise ValueError
    # ------------------------------------------------------------------

    def test_no_overlap_raises(self):
        criteria = [_criterion("a", 1.0)]
        with pytest.raises(ValueError, match="No criterion scores match"):
            ScoreCalculator(criteria).compute({"b": _score("b", 5.0)})

    def test_score_above_10_raises(self):
        criteria = [_criterion("a", 1.0)]
        with pytest.raises(ValueError, match="0.0 – 10.0"):
            ScoreCalculator(criteria).compute({"a": _score("a", 10.1)})

    def test_score_below_0_raises(self):
        criteria = [_criterion("a", 1.0)]
        with pytest.raises(ValueError, match="0.0 – 10.0"):
            ScoreCalculator(criteria).compute({"a": _score("a", -0.1)})

    def test_all_zero_weights_raises(self):
        criteria = [_criterion("a", 0.0)]
        with pytest.raises(ValueError, match="weights are 0.0"):
            ScoreCalculator(criteria).compute({"a": _score("a", 5.0)})

    def test_empty_scores_dict_raises(self):
        criteria = [_criterion("a", 1.0)]
        with pytest.raises(ValueError):
            ScoreCalculator(criteria).compute({})