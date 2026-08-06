import pytest

from sponsor_pipeline.services.sponsor_evaluator.evaluator import (
    DEVELOPER_ECOSYSTEM,
    TALENT_ACQUISITION,
)
from sponsor_pipeline.services.sponsor_evaluator.llm.sponsor_dimension_evaluator import (
    _build_dimension_prompt,
    _build_summary_prompt,
    _parse_claude_criterion_score,
    _parse_claude_summary,
    _parse_motivations,
)
from sponsor_pipeline.services.sponsor_evaluator.schemas import (
    Confidence,
    CriterionScore,
    SponsorMotivation,
)

# ------------------------------------------------------------
# Fake Response Classes
# ------------------------------------------------------------

class FakeTextBlock:
    type = "text"
    def __init__(self):
        self.text = "this is text not a tool"

class FakeToolBlock:
    type = "tool_use"
    def __init__(self):
        self.input = {
            "score": 8.5,
            "reasoning": "strong hiring signals.",
            "supporting_evidence": [
                "university recruiting page",
                "internship program",
            ],
            "motivations": ["talent"],
            "confidence": "high",
            "explanation": "...",
            "key_strengths": [],
            "potential_weaknesses": [],
            "recommended_outreach_angle": "...",
            "recommended_contact_role": "Job Title",
        }

class FakeResponseA:
    stop_reason = "tool_use"
    def __init__(self):
        self.content = [FakeToolBlock()]

class FakeResponseB:
    stop_reason = "tool_use"
    def __init__(self):
        self.content = [
            FakeTextBlock(),
            FakeToolBlock()
        ]

class FakeResponseC:
    stop_reason = "end_turn"
    def __init__(self):
        self.content = [FakeTextBlock()]

class FakeToolBlockNoEvidence:
    type = "tool_use"
    def __init__(self):
        self.input = {
            "score": 8.5,
            "reasoning": "strong hiring signals.",
            "supporting_evidence": [],
            "motivations": ["talent"],
            "confidence": "high",
            "explanation": "...",
            "key_strengths": [],
            "potential_weaknesses": [],
            "recommended_outreach_angle": "...",
            "recommended_contact_role": "Job Title",
        }

class FakeResponseNoEvidence:
    stop_reason = "tool_use"
    def __init__(self):
        self.content = [FakeToolBlockNoEvidence()]

# ------------------------------------------------------------
# Tests for Building Text Prompts
# ------------------------------------------------------------

def test_dimension_prompt_contains_company_name(sample_company, sample_evidence):
    prompt = _build_dimension_prompt(
        TALENT_ACQUISITION,
        sample_company,
        sample_evidence,
    )
    assert sample_company.name in prompt

def test_dimension_prompt_contains_criterion_details(sample_company, sample_evidence):
    prompt = _build_dimension_prompt(
        TALENT_ACQUISITION,
        sample_company,
        sample_evidence,
    )
    assert TALENT_ACQUISITION.name in prompt
    assert TALENT_ACQUISITION.description in prompt

def test_dimension_prompt_contains_primary_evidence_for_talent_acquisition(sample_company, sample_evidence):
    prompt = _build_dimension_prompt(
        TALENT_ACQUISITION,
        sample_company,
        sample_evidence,
    )
    assert "Primary evidence (directly relevant to this criterion):" in prompt
    assert "Hiring software interns in Waterloo" in prompt

def test_dimension_prompt_contains_primary_evidence_for_developer_ecosystem(sample_company, sample_evidence):
    prompt = _build_dimension_prompt(
        DEVELOPER_ECOSYSTEM,
        sample_company,
        sample_evidence,
    )
    assert "Primary evidence (directly relevant to this criterion):" in prompt
    assert "Public REST API with free tier" in prompt

def test_dimension_prompt_contains_evidence_hint(sample_company, sample_evidence):
    prompt = _build_dimension_prompt(
        TALENT_ACQUISITION,
        sample_company,
        sample_evidence,
    )
    assert "Evidence hints (what to look for):" in prompt
    assert any(
        hint in prompt
        for hint in TALENT_ACQUISITION.evidence_hints
    )

def test_dimension_prompt_contains_no_primary_evidence(sample_company):
    prompt = _build_dimension_prompt(
        TALENT_ACQUISITION,
        sample_company,
        evidence=[],
    )
    assert "Primary evidence (directly relevant to this criterion):" in prompt
    assert "none collected" in prompt

def test_prompt_includes_optional_company_fields(sample_company):
    sample_company.industry = "Software"
    sample_company.website = "https://example.com"
    sample_company.description = "Developer tools company"
    prompt = _build_dimension_prompt(
        TALENT_ACQUISITION,
        sample_company,
        [],
    )
    assert "Industry: Software" in prompt
    assert "Website: https://example.com" in prompt
    assert "Description: Developer tools company" in prompt

def test_prompt_removes_empty_company_fields(sample_company):
    sample_company.industry = ""
    sample_company.website = None
    sample_company.description = ""
    prompt = _build_dimension_prompt(
        TALENT_ACQUISITION,
        sample_company,
        [],
    )
    assert "Industry:" not in prompt
    assert "Website:" not in prompt
    assert "Description:" not in prompt

def test_summary_prompt_contains_all_dimension_scores(sample_company, sample_evidence):
    scores = {
        "talent_acquisition": CriterionScore(
            criterion_key="talent_acquisition",
            score=8.5,
            reasoning="...",
            supporting_evidence=[],
        ),
        "developer_ecosystem": CriterionScore(
            criterion_key="developer_ecosystem",
            score=7.0,
            reasoning="...",
            supporting_evidence=[],
        ),
        "community_sponsorship": CriterionScore(
            criterion_key="community_sponsorship",
            score=6.5,
            reasoning="...",
            supporting_evidence=[],
        ),
        "outreach_accessibility": CriterionScore(
            criterion_key="outreach_accessibility",
            score=9.0,
            reasoning="...",
            supporting_evidence=[],
        ),
        "sponsorship_capacity": CriterionScore(
            criterion_key="sponsorship_capacity",
            score=8.0,
            reasoning="...",
            supporting_evidence=[],
        ),
        "strategic_alignment": CriterionScore(
            criterion_key="strategic_alignment",
            score=7.5,
            reasoning="...",
            supporting_evidence=[],
        ),
    }
    prompt = _build_summary_prompt(sample_company, sample_evidence, scores)
    for score in scores.values():
        assert score.criterion_key in prompt
        assert str(score.score) in prompt

# ------------------------------------------------------------
# Tests for Claude Response Parsing
# ------------------------------------------------------------

def test_parse_claude_extracts_all_fields():
    response = FakeResponseA()
    score = _parse_claude_criterion_score(
        "talent_acquisition",
        response,
    )
    assert score.criterion_key == "talent_acquisition"
    assert score.score == 8.5
    assert score.reasoning == "strong hiring signals."
    assert score.supporting_evidence == [
        "university recruiting page",
        "internship program",
    ]

def test_parse_claude_score_is_float():
    response = FakeResponseA()
    result = _parse_claude_criterion_score(
        "talent_acquisition",
        response,
    )
    assert isinstance(result.score, float)

def test_parse_claude_defaults_missing_supporting_evidence():
    response = FakeResponseNoEvidence()
    result = _parse_claude_criterion_score(
        "talent_acquisition",
        response,
    )
    assert result.supporting_evidence == []

def test_parse_claude_finds_tool_block_after_text():
    result = _parse_claude_criterion_score(
        "talent_acquisition",
        FakeResponseB(),
    )
    assert result.score == 8.5
    assert result.reasoning == "strong hiring signals."
    assert result.supporting_evidence == [
        "university recruiting page",
        "internship program",
    ]

def test_parse_claude_raises_exception_when_no_tool_block():
    with pytest.raises(ValueError, match="Claude did not return a tool_use block"):
        _parse_claude_criterion_score(
            "talent_acquisition",
            FakeResponseC(),
        )

def test_parse_claude_summary_converts_strings_to_enums():
    response = FakeResponseA()
    summary = _parse_claude_summary(response)
    assert summary.motivations == [SponsorMotivation.TALENT]
    assert summary.confidence == Confidence.HIGH
    assert summary.explanation == "..."
    assert summary.key_strengths == []
    assert summary.potential_weaknesses == []
    assert summary.recommended_outreach_angle == "..."
    assert summary.recommended_contact_role == "Job Title"

def test_parse_motivations_ignores_invalid_values():
    result = _parse_motivations(["talent", "invalid_value", "brand_awareness"])
    assert result == [
        SponsorMotivation.TALENT,
        SponsorMotivation.BRAND_AWARENESS,
    ]

def test_parse_motivations_defaults_to_brand_awareness():
    result = _parse_motivations(
        ["wrong", "another_wrong"]
    )
    assert result == [SponsorMotivation.BRAND_AWARENESS]

def test_parse_claude_summary_raises_without_tool_block():
    with pytest.raises(ValueError, match="Claude did not return a tool_use block", ):
        _parse_claude_summary(FakeResponseC())

