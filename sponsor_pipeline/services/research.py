from __future__ import annotations

from sponsor_pipeline.llm.client import LLMClient
from sponsor_pipeline.logger import get_logger
from sponsor_pipeline.models import (
    Company,
    CrawlResult,
    SponsorReport,
    SponsorScore,
    SponsorTier,
)
from sponsor_pipeline.prompts.templates import PromptTemplateRegistry
from sponsor_pipeline.services.crawl_evidence import format_crawl_for_prompt
from sponsor_pipeline.services.filter import LeadFilter

logger = get_logger(__name__)


class CompanyResearchService:
    def __init__(
        self,
        llm: LLMClient,
        prompts: PromptTemplateRegistry,
        lead_filter: LeadFilter,
    ) -> None:

        self._llm = llm

        self._prompts = prompts

        self._lead_filter = lead_filter

    def generate_report(
        self,
        company: Company,
        score: SponsorScore,
        crawl: CrawlResult | None = None,
    ) -> SponsorReport:
        logger.info("Generating research report for %s", company.name)

        crawl_context = (
            format_crawl_for_prompt(crawl)
            if crawl
            else "No website crawl data available."
        )

        result = self._llm.complete_structured(
            self._prompts.get_research_prompt()
            + f"\n\nCompany: {company.name}\nWebsite: {company.website}\n"
            + f"Overall score: {score.overall_score}/10 (confidence: {score.confidence})\n"
            + f"Summary: {score.explanation}\n"
            + f"Key strengths: {', '.join(score.key_strengths)}\n"
            + f"Potential weaknesses: {', '.join(score.potential_weaknesses)}\n"
            + f"Recommended outreach angle: {score.recommended_outreach_angle}\n"
            + "Criterion scores:\n"
            + "".join(
                f"  - {k}: {v.score}/10 — {v.reasoning}\n"
                for k, v in score.criterion_scores.items()
            )
            + "\n"
            + f"Website research:\n{crawl_context}",
            """{

  "description": "string",

  "products_and_services": "string",

  "recent_launches": ["string"],

  "past_sponsorship_evidence": "string",

  "hires_interns_new_grads": true,

  "hires_in_canada": true,

  "waterloo_alumni_present": false,

  "has_devrel_or_recruiting_staff": true,

  "best_contact_role": "string",

  "best_sponsor_angle": "string",

  "suggested_tier": "silver"

}""",
        )

        priority = self._lead_filter.assign_priority(score)
        logger.info(
            "Research report completed for %s with %s priority",
            company.name,
            priority.value,
        )

        return SponsorReport(
            company_id=company.id,
            priority=priority,
            description=str(result.get("description", "")),
            products_and_services=str(result.get("products_and_services", "")),
            recent_launches=[str(x) for x in result.get("recent_launches", [])],
            past_sponsorship_evidence=str(result.get("past_sponsorship_evidence", "")),
            hires_interns_new_grads=bool(result.get("hires_interns_new_grads")),
            hires_in_canada=bool(result.get("hires_in_canada")),
            waterloo_alumni_present=bool(result.get("waterloo_alumni_present")),
            has_devrel_or_recruiting_staff=bool(
                result.get("has_devrel_or_recruiting_staff")
            ),
            best_sponsor_angle=str(result.get("best_sponsor_angle", "")),
            suggested_tier=_tier(result.get("suggested_tier")),
        )


def _tier(raw: object) -> SponsorTier:

    try:
        return SponsorTier(str(raw).lower())

    except ValueError:
        return SponsorTier.SILVER
