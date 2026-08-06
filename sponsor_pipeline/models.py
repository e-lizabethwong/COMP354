"""
Domain models for the HackCanada sponsor research pipeline.
Defines all data classes and uses enumerations to maintain fixed set of values for each.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

# Enumerations -----------------


class DiscoverySource(str, Enum):
    """
    Where a company was found during the discovery part of the pipeline.
    """

    MLH_EVENT = "mlh_event"
    HACKATHON_WEBSITE = "hackathon_website"
    DEVPOST = "devpost"
    JOB_POSTING = "job_posting"
    PRODUCT_LAUNCH = "product_launch"
    CANADIAN_RECRUITING = "canadian_recruiting"
    MANUAL_INPUT = "manual_input"


# ------------------------------


@dataclass
class RawLead:
    """
    Unnormalized company lead emitted by discovery source adapters.
    """

    name: str
    website: str = ""
    source: DiscoverySource = DiscoverySource.MANUAL_INPUT
    notes: str = ""


# ------------------------------


class LeadStatus(str, Enum):
    """
    Tracks where a company is in the pipeline at any given moment.
    """

    DISCOVERED = "discovered"
    SCORED = "scored"
    FILTERED_OUT = "filtered_out"
    RESEARCHED = "researched"
    CONTACTS_FOUND = "contacts_found"
    OUTREACH_READY = "outreach_ready"


# ------------------------------


class CompanySize(str, Enum):
    """
    Size classification used for scoring:
    - Too Small => low budget
    - Sweet Spot => best targets
    - Too Big => hard to reach
    """

    TOO_SMALL = "too_small"
    SWEET_SPOT = "sweet_spot"
    TOO_BIG = "too_big"
    UNKNOWN = "unknown"


# ------------------------------


class SponsorMotivation(str, Enum):
    """
    Why a company would want to be a sponsor (core of the scoring model)
    """

    HIRING_TALENT = "hiring_talent"
    DEVELOPER_ADOPTION = "developer_adoption"
    BRAND_COMMUNITY = "brand_community"


# ------------------------------


class ContactMethodType(str, Enum):
    """
    How to reach a contact person used by ContactDiscoveryService
    """

    EMAIL = "email"
    LINKEDIN = "linkedin"
    X_TWITTER = "x_twitter"
    GITHUB = "github"
    PERSONAL_WEBSITE = "personal_website"
    TEAM_PAGE = "team_page"
    BLOG_AUTHOR = "blog_author"
    CONFERENCE_SPEAKER = "conference_speaker"
    COMMUNITY_PAGE = "community_page"


# ------------------------------


class ContactRole(str, Enum):
    """
    The role of the person being contacted at a company
    """

    DEVREL = "devrel"
    DEV_ADVOCATE = "dev_advocate"
    COMMUNITY_MANAGER = "community_manager"
    DEV_MARKETING = "dev_marketing"
    CAMPUS_RECRUITER = "campus_recruiter"
    UNIVERSITY_RECRUITER = "university_recruiter"
    PARTNERSHIPS = "partnerships"
    FOUNDER_CEO = "founder_ceo"
    OTHER = "other"


# ------------------------------


class EvidenceCategory(str, Enum):
    """
    Categories of evidence when scoring a company and used by SponsorScoringService
    """

    PAST_SPONSORSHIP = "past_sponsorship"
    WATERLOO_CANADA_FIT = "waterloo_canada_fit"
    DEVELOPER_PRODUCT_FIT = "developer_product_fit"
    HIRING_SIGNAL = "hiring_signal"
    CONTACTABILITY = "contactability"


# ------------------------------


class SponsorTier(str, Enum):
    """
    Sponsorship package tier to pitch to a company
    """

    TITLE = "title"
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    IN_KIND = "in_kind"


# ------------------------------


class Priority(str, Enum):
    """
    Priority level assigned after scoring and filtering
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ------------------------------


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# Pipeline entities -------------


@dataclass
class Company:
    """
    Normalized company record used throughout the sponsor pipeline.
    """

    name: str
    website: str = ""
    industry: str = ""
    company_size: CompanySize = CompanySize.UNKNOWN
    discovery_sources: list[DiscoverySource] = field(
        default_factory=lambda: [DiscoverySource.MANUAL_INPUT]
    )
    status: LeadStatus = LeadStatus.DISCOVERED
    id: str = field(default_factory=lambda: _new_id("company"))
    created_at: datetime = field(default_factory=_now_utc)


@dataclass
class Evidence:
    """
    Tagged observation collected from crawling or research.
    """

    category: EvidenceCategory
    description: str
    source_url: str = ""
    extracted_at: datetime = field(default_factory=_now_utc)


@dataclass
class CrawlResult:
    """
    Website crawl output consumed by scoring, research, and contact discovery.
    """

    start_url: str
    pages_crawled: int = 0
    emails: list[str] = field(default_factory=list)
    social_links: list[ContactMethod] = field(default_factory=list)
    page_snippets: dict[str, str] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class CriterionScore:
    """
    Score for a single evaluation dimension produced by the sponsor evaluator.
    """

    criterion_key: str
    score: float
    reasoning: str
    supporting_evidence: list[str] = field(default_factory=list)


@dataclass
class SponsorScore:
    """
    The complete evaluation result for one company.
    Replaces the previous 5-field fixed scoring model with richer evaluator output:
    per-dimension reasoning, confidence level, key strengths, weaknesses, and outreach angle are now all preserved.
    """

    company: Company
    criterion_scores: dict[str, CriterionScore]
    overall_score: float
    motivations: list[SponsorMotivation]
    confidence: str
    explanation: str
    key_strengths: list[str] = field(default_factory=list)
    potential_weaknesses: list[str] = field(default_factory=list)
    recommended_outreach_angle: str = ""
    recommended_contact_role: str = ""
    scored_at: datetime = field(default_factory=_now_utc)


@dataclass
class SponsorReport:
    """
    Narrative sponsorship research report for an evaluated company.
    """

    company_id: str
    priority: Priority = Priority.LOW
    description: str = ""
    products_and_services: str = ""
    recent_launches: list[str] = field(default_factory=list)
    past_sponsorship_evidence: str = ""
    hires_interns_new_grads: bool = False
    hires_in_canada: bool = False
    waterloo_alumni_present: bool = False
    has_devrel_or_recruiting_staff: bool = False
    best_sponsor_angle: str = ""
    suggested_tier: SponsorTier = SponsorTier.SILVER
    generated_at: datetime = field(default_factory=_now_utc)


@dataclass
class ContactMethod:
    """
    Publicly discoverable way to reach a person or company.
    """

    type: ContactMethodType
    value: str
    source_url: str = ""
    confidence: float = 0.5
    is_public: bool = True


@dataclass
class ContactPerson:
    """
    Candidate person to contact for sponsorship outreach.
    """

    company_id: str
    full_name: str
    title: str = ""
    role_category: ContactRole = ContactRole.OTHER
    relevance_score: float = 0.0
    selection_rationale: str = ""
    contact_methods: list[ContactMethod] = field(default_factory=list)
    id: str = field(default_factory=lambda: _new_id("contact"))


@dataclass
class OutreachProspect:
    """
    Fully prepared outreach target with company, scoring, report, and contact data.
    """

    company: Company
    report: SponsorReport
    score: SponsorScore
    primary_contact: ContactPerson
    contact_methods: list[ContactMethod] = field(default_factory=list)


@dataclass
class PipelineResult:
    """
    Summary returned by a full pipeline run.
    """

    discovered: int = 0
    scored: int = 0
    filtered_out: int = 0
    researched: int = 0
    outreach_ready: int = 0
    prospects: list[OutreachProspect] = field(default_factory=list)

    def to_dict(self) -> dict[str, int]:
        return {
            "discovered": self.discovered,
            "scored": self.scored,
            "filtered_out": self.filtered_out,
            "researched": self.researched,
            "outreach_ready": self.outreach_ready,
        }
