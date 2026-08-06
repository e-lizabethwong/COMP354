from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from sponsor_pipeline.adapters.sources import SourceAdapter
from sponsor_pipeline.llm.client import LLMClient
from sponsor_pipeline.logger import get_logger
from sponsor_pipeline.models import Company, DiscoverySource, RawLead
from sponsor_pipeline.prompts.templates import PromptTemplateRegistry

logger = get_logger(__name__)


class CompanyDiscoveryService:
    def __init__(
        self,
        adapters: list[SourceAdapter],
        llm: LLMClient,
        prompts: PromptTemplateRegistry,
    ) -> None:
        self._adapters = adapters
        self._llm = llm
        self._prompts = prompts

    def discover_companies(
        self, sources: list[DiscoverySource] | None = None
    ) -> list[Company]:
        raw_leads: list[RawLead] = []
        for adapter in self._adapters:
            if sources and adapter.get_source_type() not in sources:
                logger.debug(
                    "Skipping discovery adapter: %s",
                    adapter.get_source_type().value,
                )
                continue
            source = adapter.get_source_type().value
            logger.info("Fetching discovery candidates from %s", source)
            candidates = adapter.fetch_candidates()
            logger.info("Fetched %s raw lead(s) from %s", len(candidates), source)
            raw_leads.extend(candidates)

        companies = self._enrich_with_ai(raw_leads)
        deduped = _dedupe_companies(companies)
        logger.info(
            "Discovery normalization produced %s company record(s), %s after dedupe",
            len(companies),
            len(deduped),
        )
        return deduped

    def enrich_from_web(self, company: Company) -> Company:
        if company.website:
            logger.debug(
                "Website already known for %s: %s", company.name, company.website
            )
            return company
        logger.info("Finding official website for %s", company.name)
        result = self._llm.complete_structured(
            self._prompts.get_discovery_prompt()
            + f"\n\nFind the official website URL for: {company.name}",
            '{"website": "https://example.com"}',
        )
        website = str(result.get("website", "")).strip()
        if website.startswith("http"):
            company.website = website
            logger.info("Found website for %s: %s", company.name, website)
        else:
            logger.warning("Could not find website for %s", company.name)
        return company

    def _enrich_with_ai(self, leads: list[RawLead]) -> list[Company]:
        if not leads:
            return []

        companies: list[Company] = []
        batch_size = 25
        for i in range(0, len(leads), batch_size):
            batch = leads[i : i + batch_size]
            logger.info(
                "Normalizing discovery leads with AI: batch %s-%s of %s",
                i + 1,
                min(i + batch_size, len(leads)),
                len(leads),
            )
            payload = [
                {
                    "name": lead.name,
                    "website": lead.website,
                    "source": lead.source.value,
                    "notes": lead.notes,
                }
                for lead in batch
            ]
            result = self._llm.complete(
                self._prompts.get_discovery_prompt()
                + "\n\nNormalize and filter this lead list. Drop weak or duplicate leads."
                + "\nReturn JSON only with shape: "
                '{"companies": [{"name": "string", "website": "https://...", '
                '"sources": ["mlh_event"], "industry": "string", "notes": "string"}]}'
                + "\n\nLeads:\n"
                + json.dumps(payload, indent=2),
            )
            parsed = _safe_parse(result)
            for item in parsed.get("companies", []):
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                website = str(item.get("website", "")).strip()
                sources_raw = item.get("sources") or [
                    item.get("source", "manual_input")
                ]
                sources_list = []
                for s in sources_raw:
                    try:
                        sources_list.append(DiscoverySource(str(s)))
                    except ValueError:
                        sources_list.append(DiscoverySource.MANUAL_INPUT)
                companies.append(
                    Company(
                        name=name,
                        website=website if website.startswith("http") else "",
                        industry=str(item.get("industry", "")),
                        discovery_sources=sources_list
                        or [DiscoverySource.MANUAL_INPUT],
                    )
                )
        return companies


def _dedupe_companies(companies: list[Company]) -> list[Company]:
    deduped: list[Company] = []
    for company in companies:
        matched = False
        comp_key = _company_key(company)
        comp_norm_name = _normalize_name(company.name)

        for existing in deduped:
            exist_key = _company_key(existing)
            exist_norm_name = _normalize_name(existing.name)

            # Match on domain key or normalized name / fuzzy similarity
            if (comp_key and comp_key == exist_key) or _is_fuzzy_match(
                comp_norm_name, exist_norm_name
            ):
                matched = True
                for source in company.discovery_sources:
                    if source not in existing.discovery_sources:
                        existing.discovery_sources.append(source)
                if not existing.website and company.website:
                    existing.website = company.website
                if not existing.industry and company.industry:
                    existing.industry = company.industry
                break

        if not matched:
            deduped.append(company)
    return deduped


CORPORATE_SUFFIXES_RE = re.compile(
    r"\b(inc|inc\.|llc|corp|corp\.|corporation|ltd|ltd\.|co|co\.|canada|technologies|software|solutions)\b",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    cleaned = CORPORATE_SUFFIXES_RE.sub("", name)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return " ".join(cleaned.lower().split())


def _company_key(company: Company) -> str:
    if company.website:
        host = urlparse(company.website).netloc.replace("www.", "").lower()
        if host:
            return host
    return _normalize_name(company.name)


def _is_fuzzy_match(name1: str, name2: str, threshold: float = 0.85) -> bool:
    if not name1 or not name2:
        return False
    if name1 == name2 or name1 in name2 or name2 in name1:
        return True
    import difflib

    return difflib.SequenceMatcher(None, name1, name2).ratio() >= threshold


def _safe_parse(text: str) -> dict:
    import re

    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse AI JSON response; returning empty lead list")
        return {"companies": []}

