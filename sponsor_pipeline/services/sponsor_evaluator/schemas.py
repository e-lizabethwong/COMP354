"""
Data structures for the sponsor evaluator module

the file contains  data definitions only,
Every other file in this module imports from here
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ----------------------------------------
# Input schemas
# ----------------------------------------


@dataclass
class Company:
    """
    Basic identifying information about a potential sponsor
    Populated by the discovery stage before the evaluator runs.
    All fields except `name` are optional since discovery quality varies.
    """

    name: str
    website: str = ""
    industry: str = ""
    description: str = ""


@dataclass
class Evidence:
    """
    Facts collected about a company during the discovery and research stages.
    Each field is a list of plain text observations, keeping them as strings
    (instead of nested objects) so that the evaluator can feed them directly
    into an LLM prompt without any extra transformation.

    Fields map to the six evaluation criteria in criteria.py,  a field being
    empty does not mean the criterion scores zero, the LLM may still infer
    from other fields, empty lists are the safe default.
    """

    # Talent Acquisition Fit
    hiring_signals: list[str] = field(default_factory=list)
    """ex: 'Hiring software interns in Waterloo', 'Campus recruiter on LinkedIn'"""

    # Developer Ecosystem Fit
    developer_products: list[str] = field(default_factory=list)
    """ ex: 'Public REST API with free tier', 'Open-source SDK on GitHub'"""

    # Community Sponsorship Fit
    past_sponsorships: list[str] = field(default_factory=list)
    """ex: 'Gold sponsor at HackTheNorth 2024', 'Listed on MLH season page'"""

    # Outreach Accessibility
    contact_signals: list[str] = field(default_factory=list)
    """ex: 'DevRel manager active on X', 'partnerships@company.com listed on site'"""

    # Sponsorship Capacity
    company_size_signals: list[str] = field(default_factory=list)
    """ex: 'Series B, ~150 employees', 'Recently raised $20M'"""

    # Strategic Alignment
    canada_signals: list[str] = field(default_factory=list)
    """ex: 'Toronto office', 'Waterloo co-op program listed on careers page'"""


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------


class Confidence(str, Enum):
    """
    How much evidence was available to support the evaluation.
    The LLM assigns this based on the volume and quality of evidence provided.
    A LOW confidence score does not mean the company is a bad sponsor but it means
    there was not enough information to be certain either way.
    """

    LOW = "low"  # Sparse evidence; score may not reflect reality
    MEDIUM = "medium"  # Reasonable evidence; score is likely directionally correct
    HIGH = "high"  # Strong evidence; score is well-supported


class SponsorMotivation(str, Enum):
    """
    The primary reason(s) a company would sponsor Hack Canada.
    A company can have more than one motivation, these map to
    the categories described in the AI Prompting System.txt
    """

    TALENT = "talent"  # wants to recruit students
    DEVELOPER_ADOPTION = (
        "developer_adoption"  # wants students building with their product
    )
    BRAND_AWARENESS = (
        "brand_awareness"  # wants visibility in the Canadian student tech scene
    )


@dataclass
class CriterionScore:
    """
    The evaluation result for a single scoring dimension.
    Produced by the LLM for each of the six criteria defined in criteria.py.
    The "criterion_key" ties this score back to its EvaluationCriterion.
    """

    criterion_key: str
    """ Matches EvaluationCriterion.key from criteria.py."""

    score: float
    """ 0.0 – 10.0. Must be grounded in evidence rather than company reputation."""

    reasoning: str
    """ One to three sentences explaining why this score was assigned."""

    supporting_evidence: list[str] = field(default_factory=list)
    """ The specific evidence items from Evidence that justify the score."""


@dataclass
class SponsorScore:
    """
    The complete evaluation result for one company.
    this is the module's output, structured so it can be displayed
    in the CLI, saved to the persistence layer, or consumed by the export module
    without further transformation.
    """

    company: Company

    criterion_scores: dict[str, CriterionScore]
    """ Keyed by criterion_key, always contains one entry per criterion in CRITERIA."""

    overall_score: float
    """ Weighted average of criterion scores, computed by scoring.py (0.0 – 10.0)."""

    motivations: list[SponsorMotivation]
    """ Why this company would sponsor, may contain multiple motivations."""

    confidence: Confidence
    """ How well supported this evaluation is by the available evidence."""

    explanation: str
    """  A short paragraph summarising the overall evaluation for a human reader."""

    key_strengths: list[str]
    """ The strongest reasons this company is worth pursuing."""

    potential_weaknesses: list[str]
    """  Risks or gaps that may make this company harder to close."""

    recommended_outreach_angle: str
    """ The specific pitch angle most likely to resonate with this company."""

    recommended_contact_role: str
    """ sThe job title or role at this company most likely to own the sponsorship decision."""
