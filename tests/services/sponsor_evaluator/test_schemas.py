from __future__ import annotations

import pytest

from sponsor_pipeline.services.sponsor_evaluator.schemas import (
    Company,
    Confidence,
    CriterionScore,
    Evidence,
    SponsorMotivation,
)

# ------------------------------------------------------------
# Test Company Input Schema
# ------------------------------------------------------------


def test_company_required_name_field():
    company = Company(name="ABC")
    assert company.name == "ABC"
    assert company.website == ""
    assert company.industry == ""
    assert company.description == ""


def test_company_optional_fields():
    company = Company(
        name="ABC",
        website="https://abc.com",
        industry="technology",
        description="it is a company",
    )
    assert company.website == "https://abc.com"
    assert company.industry == "technology"
    assert company.description == "it is a company"


# ------------------------------------------------------------
# Test Evidence Input Schema
# ------------------------------------------------------------


def test_evidence_empty_defaults():
    evidence = Evidence()
    assert evidence.hiring_signals == []
    assert evidence.developer_products == []
    assert evidence.past_sponsorships == []
    assert evidence.contact_signals == []
    assert evidence.company_size_signals == []
    assert evidence.canada_signals == []


def test_evidence_list_independence():
    first = Evidence()
    second = Evidence()
    first.hiring_signals.append("hiring interns")
    assert first.hiring_signals == ["hiring interns"]
    assert second.hiring_signals == []


def test_evidence_accepts_values():
    evidence = Evidence(
        hiring_signals=["hiring interns"],
        developer_products=["public API"],
        past_sponsorships=["hackathon sponsor"],
    )
    assert evidence.hiring_signals == ["hiring interns"]
    assert evidence.developer_products == ["public API"]
    assert evidence.past_sponsorships == ["hackathon sponsor"]


# ------------------------------------------------------------
# Test the Enums
# ------------------------------------------------------------


def test_confidence_values():
    assert Confidence.LOW.value == "low"
    assert Confidence.MEDIUM.value == "medium"
    assert Confidence.HIGH.value == "high"

def test_invalid_confidence_values():
    with pytest.raises(ValueError):
        Confidence("Not")

def test_invalid_confidence_values_capitals():
    with pytest.raises(ValueError):
        Confidence("High")

def test_sponsor_motivation_values():
    assert SponsorMotivation.TALENT.value == "talent"
    assert SponsorMotivation.DEVELOPER_ADOPTION.value == "developer_adoption"
    assert SponsorMotivation.BRAND_AWARENESS.value == "brand_awareness"


def test_invalid_sponsor_motivation_values():
    with pytest.raises(ValueError):
        SponsorMotivation("Skill")


def test_invalid_sponsor_motivation_values_capitals():
    with pytest.raises(ValueError):
        SponsorMotivation("Talent")

# ------------------------------------------------------------
# Tests for CriterionScore
# ------------------------------------------------------------


def test_criterion_score_default_fields():
    score = CriterionScore(
        criterion_key="talent",
        score=8.0,
        reasoning="Strong hiring signals",
    )
    assert score.supporting_evidence == []

def test_criterion_score_optional_field():
    score = CriterionScore(
        criterion_key="talent",
        score=8.0,
        reasoning="strong hiring signals",
        supporting_evidence=["hiring interns"],
    )
    assert score.criterion_key == "talent"
    assert score.score == 8.0
    assert score.reasoning == "strong hiring signals"
    assert score.supporting_evidence == ["hiring interns"]

def test_criterion_score_independence():
    first = CriterionScore(
        criterion_key="talent",
        score=8.0,
        reasoning="Strong hiring signals",
    )
    second = CriterionScore(
        criterion_key="talent",
        score=8.0,
        reasoning="Strong hiring signals",
    )
    first.supporting_evidence.append("hiring interns")
    assert first.supporting_evidence == ["hiring interns"]
    assert second.supporting_evidence == []
