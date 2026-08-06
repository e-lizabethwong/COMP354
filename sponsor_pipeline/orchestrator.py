from __future__ import annotations

from pathlib import Path

from sponsor_pipeline.adapters.sources import (
    HackathonSiteAdapter,
    JobBoardAdapter,
    MLHSourceAdapter,
    ProductLaunchAdapter,
)
from sponsor_pipeline.config import Settings
from sponsor_pipeline.export.reporter import ReportExporter
from sponsor_pipeline.llm.client import LLMClient
from sponsor_pipeline.logger import get_logger
from sponsor_pipeline.models import (
    Company,
    CrawlResult,
    DiscoverySource,
    LeadStatus,
    OutreachProspect,
    PipelineResult,
)
from sponsor_pipeline.persistence.repository import SponsorRepository
from sponsor_pipeline.prompts.templates import PromptTemplateRegistry
from sponsor_pipeline.services.contacts import ContactDiscoveryService
from sponsor_pipeline.services.discovery import CompanyDiscoveryService
from sponsor_pipeline.services.filter import LeadFilter
from sponsor_pipeline.services.outreach import OutreachService
from sponsor_pipeline.services.research import CompanyResearchService
from sponsor_pipeline.services.scoring import SponsorScoringService
from sponsor_pipeline.services.scraper import WebScraperService, normalize_url
from sponsor_pipeline.services.sponsor_evaluator import (
    ClaudeSponsorDimensionEvaluator,
    GoogleSponsorDimensionEvaluator,
    OpenAISponsorDimensionEvaluator,
    SponsorEvaluator,
)
from sponsor_pipeline.services.sponsor_evaluator.bridge import (
    crawl_to_evidence,
    evaluator_score_to_pipeline,
    pipeline_company_to_evaluator,
)
from sponsor_pipeline.services.sponsor_evaluator.llm.sponsor_dimension_evaluator import (
    SponsorDimensionEvaluator,
)


def _build_dimension_evaluator(settings: Settings) -> SponsorDimensionEvaluator:
    """
    factory that creates the right LLM evaluator based on the LLM_PROVIDER setting

    lazy imports (import inside the if-branch)
    only import the SDK for the provider the user actually configured

    Each branch:
        anthropic : creates an anthropic.Anthropic client and passes it to Claude evaluator
        openai    : creates an openai.OpenAI client and passes it to OpenAI evaluator
        google    : configures genai globally with the API key, passes the module to Google evaluator
    """
    provider = settings.llm_provider
    model = settings.llm_model

    if provider == "anthropic":
        import anthropic

        return ClaudeSponsorDimensionEvaluator(
            anthropic.Anthropic(api_key=settings.anthropic_api_key),
            model,
        )

    if provider == "openai":
        from openai import OpenAI

        return OpenAISponsorDimensionEvaluator(
            OpenAI(api_key=settings.openai_api_key),
            model,
        )

    if provider == "google":
        # Uses the new google.genai SDK (google-genai package), not the deprecated google.generativeai
        from google import genai

        client = genai.Client(api_key=settings.google_api_key)
        return GoogleSponsorDimensionEvaluator(client, model)

    # raise as a safety net
    raise ValueError(
        f"Unsupported LLM provider for the evaluator: '{provider}'. "
        f"Choose one of: anthropic, openai, google"
    )


logger = get_logger(__name__)


class PipelineOrchestrator:
    def __init__(self, settings: Settings) -> None:
        logger.info("Setting up pipeline services")
        self._settings = settings
        self._llm = LLMClient(settings)
        self._prompts = PromptTemplateRegistry(settings.event_name)
        self._repo = SponsorRepository(settings.sponsor_db_path)
        self._scraper = WebScraperService(settings)
        self._crawl_cache: dict[str, CrawlResult] = {}
        self._discovery = CompanyDiscoveryService(
            self._build_adapters(settings), self._llm, self._prompts
        )
        self._scoring = SponsorScoringService()
        # Pick the right LLM evaluator based on whatever provider is set in .env
        self._evaluator = SponsorEvaluator(_build_dimension_evaluator(settings))
        self._filter = LeadFilter(self._scoring, settings.min_overall_score)
        self._research = CompanyResearchService(self._llm, self._prompts, self._filter)
        self._contacts = ContactDiscoveryService(
            self._llm, self._scraper, self._prompts
        )
        self._exporter = ReportExporter()
        self._outreach = OutreachService(settings, self._repo)
        logger.info("Pipeline services ready")

    def run_full_pipeline(
        self, sources: list[DiscoverySource] | None = None
    ) -> PipelineResult:
        logger.info("Starting full pipeline")
        companies = self.run_discovery(sources)
        scored = self.run_scoring(companies)
        passed, rejected = self._filter.filter_by_threshold(scored)
        logger.info(
            "Filter result: %s passed, %s rejected below threshold %.1f",
            len(passed),
            len(rejected),
            self._settings.min_overall_score,
        )
        for company in rejected:
            company.status = LeadStatus.FILTERED_OUT
            self._repo.save_company(company)
        researched = self.run_research(passed)
        prospects = self.run_contact_discovery(researched)
        result = PipelineResult(
            discovered=len(companies),
            scored=len(scored),
            filtered_out=len(rejected),
            researched=len(researched),
            outreach_ready=len(prospects),
            prospects=prospects,
        )
        logger.info(
            "Full pipeline finished: discovered=%s, scored=%s, researched=%s, outreach_ready=%s",
            result.discovered,
            result.scored,
            result.researched,
            result.outreach_ready,
        )
        return result

    def run_discovery(
        self, sources: list[DiscoverySource] | None = None
    ) -> list[Company]:
        selected = ", ".join(source.value for source in sources) if sources else "all"
        logger.info("Discovery started using sources: %s", selected)
        companies = self._discovery.discover_companies(sources)
        logger.info("Discovery returned %s unique candidate(s)", len(companies))
        enriched: list[Company] = []
        for index, company in enumerate(companies, start=1):
            logger.info(
                "Enriching discovered company %s/%s: %s",
                index,
                len(companies),
                company.name,
            )
            company = self._discovery.enrich_from_web(company)
            company.status = LeadStatus.DISCOVERED
            self._repo.save_company(company)
            enriched.append(company)
        logger.info("Discovery finished with %s saved company record(s)", len(enriched))
        return enriched

    def run_scoring(self, companies: list[Company] | None = None) -> list[Company]:
        targets = companies or self._repo.get_companies(LeadStatus.DISCOVERED)
        logger.info("Scoring started for %s company candidate(s)", len(targets))
        scored: list[Company] = []
        for index, company in enumerate(targets, start=1):
            logger.info("Scoring company %s/%s: %s", index, len(targets), company.name)
            if not company.website:
                logger.info(
                    "No website for %s; attempting web enrichment", company.name
                )
                company = self._discovery.enrich_from_web(company)
            if not company.website:
                logger.warning("Skipping %s because no website was found", company.name)
                continue
            crawl = self._get_crawl(company.website)
            self._repo.save_evidence(company.id, crawl.evidence)
            eval_score = self._evaluator.evaluate(
                pipeline_company_to_evaluator(company),
                crawl_to_evidence(crawl),
            )
            score = evaluator_score_to_pipeline(company, eval_score)
            logger.info(
                "Score for %s: %.1f/10 (%s)",
                company.name,
                score.overall_score,
                score.confidence,
            )
            company.status = LeadStatus.SCORED
            self._repo.save_company(company)
            self._repo.save_score(score)
            self._scoring.load_scores([score])
            scored.append(company)
        logger.info("Scoring finished with %s scored company record(s)", len(scored))
        return scored

    def run_research(self, companies: list[Company] | None = None) -> list[Company]:
        if companies is None:
            logger.info("Loading saved scores for research")
            self._scoring.load_scores(self._repo.get_scores())
            all_scored = self._repo.get_companies(LeadStatus.SCORED)
            companies, _ = self._filter.filter_by_threshold(all_scored)
            logger.info(
                "Research selected %s company candidate(s) above threshold %.1f",
                len(companies),
                self._settings.min_overall_score,
            )
        else:
            logger.info(
                "Research started for %s provided company candidate(s)", len(companies)
            )

        researched: list[Company] = []
        for index, company in enumerate(companies, start=1):
            logger.info(
                "Researching company %s/%s: %s", index, len(companies), company.name
            )
            score = self._scoring.get_score(company.id) or self._repo.get_score(
                company.id
            )
            if not score:
                logger.warning(
                    "Skipping research for %s because no score was found", company.name
                )
                continue
            crawl = self._get_crawl(company.website) if company.website else None
            report = self._research.generate_report(company, score, crawl)
            company.status = LeadStatus.RESEARCHED
            self._repo.save_company(company)
            self._repo.save_report(report)
            researched.append(company)
            logger.info(
                "Research report saved for %s with %s priority",
                company.name,
                report.priority.value,
            )
        logger.info("Research finished with %s report(s)", len(researched))
        return researched

    def run_contact_discovery(
        self, companies: list[Company] | None = None
    ) -> list[OutreachProspect]:
        targets = companies or self._repo.get_companies(LeadStatus.RESEARCHED)
        logger.info(
            "Contact discovery started for %s company candidate(s)", len(targets)
        )
        prospects: list[OutreachProspect] = []
        for index, company in enumerate(targets, start=1):
            logger.info("Finding contacts %s/%s: %s", index, len(targets), company.name)
            report = self._repo.get_report(company.id)
            score = self._scoring.get_score(company.id) or self._repo.get_score(
                company.id
            )
            if not report or not score or not company.website:
                logger.warning(
                    "Skipping contact discovery for %s because report, score, or website is missing",
                    company.name,
                )
                continue
            crawl = self._get_crawl(company.website)
            contacts = self._contacts.find_key_contacts(company, report, crawl)
            if not contacts:
                logger.warning("No contacts found for %s", company.name)
                continue
            primary = contacts[0]
            methods = self._contacts.find_public_contact_info(primary, company, crawl)
            primary.contact_methods = methods
            self._repo.save_contact(primary)
            company.status = LeadStatus.OUTREACH_READY
            self._repo.save_company(company)
            prospects.append(
                OutreachProspect(
                    company=company,
                    report=report,
                    score=score,
                    primary_contact=primary,
                    contact_methods=methods,
                )
            )
            logger.info(
                "Primary contact for %s: %s (%s method(s))",
                company.name,
                primary.full_name,
                len(methods),
            )
        logger.info(
            "Contact discovery finished with %s outreach-ready prospect(s)",
            len(prospects),
        )
        return prospects

    def export_reports(self, output_dir: str | Path) -> None:
        logger.info("Exporting reports to %s", output_dir)
        self._exporter.export_all(self._repo, Path(output_dir))
        logger.info("Report export finished")

    def generate_outreach_emails(self, output_dir: str | Path) -> int:
        logger.info("Generating outreach emails in %s", output_dir)
        count = self._outreach.generate_all_and_save(Path(output_dir))
        logger.info("Outreach email generation complete: %s files generated", count)
        return count

    def _get_crawl(self, website: str) -> CrawlResult:
        key = normalize_url(website)
        if key not in self._crawl_cache:
            logger.info("Crawling website: %s", key)
            self._crawl_cache[key] = self._scraper.crawl_site(website)
        else:
            logger.debug("Using cached crawl for %s", key)
        return self._crawl_cache[key]

    @staticmethod
    def _build_adapters(settings: Settings) -> list:
        hackathon_urls: list[str] = []
        if settings.hackathon_urls_file.exists():
            hackathon_urls = [
                line.strip()
                for line in settings.hackathon_urls_file.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip() and not line.startswith("#")
            ]
        logger.info(
            "Loaded %s hackathon URL(s) from %s",
            len(hackathon_urls),
            settings.hackathon_urls_file,
        )
        return [
            MLHSourceAdapter(settings.mlh_events_url),
            HackathonSiteAdapter(hackathon_urls),
            JobBoardAdapter(),
            ProductLaunchAdapter(),
        ]
