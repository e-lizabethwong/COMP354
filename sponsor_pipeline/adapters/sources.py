from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import ClassVar
from urllib.parse import urljoin, urlparse

import requests

from sponsor_pipeline.logger import get_logger
from sponsor_pipeline.models import DiscoverySource, RawLead

logger = get_logger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


def fetch_url(url: str, timeout: int = 20) -> str:
    logger.debug("Fetching URL: %s", url)
    response = SESSION.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_links(html: str, base_url: str) -> list[str]:
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    links: list[str] = []
    for href in hrefs:
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme in {"http", "https"}:
            links.append(absolute)
    return links


def strip_html(html: str, max_chars: int = 12000) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


class SourceAdapter(ABC):
    @abstractmethod
    def fetch_candidates(self) -> list[RawLead]:
        raise NotImplementedError

    @abstractmethod
    def get_source_type(self) -> DiscoverySource:
        raise NotImplementedError


class MLHSourceAdapter(SourceAdapter):
    def __init__(self, events_url: str) -> None:
        self._events_url = events_url

    def get_source_type(self) -> DiscoverySource:
        return DiscoverySource.MLH_EVENT

    def fetch_candidates(self) -> list[RawLead]:
        logger.info("Fetching MLH events from %s", self._events_url)
        html = fetch_url(self._events_url)
        event_links = [
            link
            for link in extract_links(html, self._events_url)
            if "localhackday" in link.lower()
            or "hackathon" in link.lower()
            or "/events/" in link
        ][:15]

        leads: list[RawLead] = []
        seen: set[str] = set()
        for event_url in event_links:
            try:
                logger.info("Inspecting MLH event page: %s", event_url)
                event_html = fetch_url(event_url)
            except requests.RequestException as exc:
                logger.warning("Failed to fetch MLH event page %s: %s", event_url, exc)
                continue
            sponsor_section = _extract_sponsor_section(event_html)
            for name in _guess_company_names(sponsor_section):
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                leads.append(
                    RawLead(
                        name=name,
                        website="",
                        source=DiscoverySource.MLH_EVENT,
                        notes=f"Seen on MLH event page: {event_url}",
                    )
                )
        logger.info("MLH adapter produced %s raw lead(s)", len(leads))
        return leads


class HackathonSiteAdapter(SourceAdapter):
    def __init__(self, urls: list[str]) -> None:
        self._urls = urls

    def get_source_type(self) -> DiscoverySource:
        return DiscoverySource.HACKATHON_WEBSITE

    def fetch_candidates(self) -> list[RawLead]:
        leads: list[RawLead] = []
        seen: set[str] = set()
        for url in self._urls:
            try:
                logger.info("Inspecting hackathon sponsor page: %s", url)
                html = fetch_url(url)
            except requests.RequestException as exc:
                logger.warning("Failed to fetch hackathon page %s: %s", url, exc)
                continue
            sponsor_section = _extract_sponsor_section(html)
            for name in _guess_company_names(sponsor_section):
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                leads.append(
                    RawLead(
                        name=name,
                        website="",
                        source=DiscoverySource.HACKATHON_WEBSITE,
                        notes=f"Listed as sponsor on {url}",
                    )
                )
        logger.info("Hackathon site adapter produced %s raw lead(s)", len(leads))
        return leads


class JobBoardAdapter(SourceAdapter):
    """Seed list of Canadian tech employers commonly hiring students."""

    SEED_COMPANIES: ClassVar[list[tuple[str, str]]] = [
        ("Shopify", "https://www.shopify.com"),
        ("Wealthsimple", "https://www.wealthsimple.com"),
        ("1Password", "https://1password.com"),
        ("Ada", "https://www.ada.cx"),
        ("Cohere", "https://cohere.com"),
        ("Hopper", "https://www.hopper.com"),
        ("Hootsuite", "https://www.hootsuite.com"),
        ("Clio", "https://www.clio.com"),
        ("ApplyBoard", "https://www.applyboard.com"),
        ("PointClickCare", "https://www.pointclickcare.com"),
        ("DRW", "https://www.drw.com"),
        ("Citadel", "https://www.citadel.com"),
        ("RBC", "https://www.rbc.com"),
        ("TD Bank", "https://www.td.com"),
    ]

    def get_source_type(self) -> DiscoverySource:
        return DiscoverySource.JOB_POSTING

    def fetch_candidates(self) -> list[RawLead]:
        logger.info("Using %s seeded job-board/company leads", len(self.SEED_COMPANIES))
        return [
            RawLead(
                name=name,
                website=website,
                source=DiscoverySource.JOB_POSTING,
                notes="Canadian tech employer with intern/new grad hiring signals",
            )
            for name, website in self.SEED_COMPANIES
        ]


class ProductLaunchAdapter(SourceAdapter):
    """Developer-facing companies with strong hackathon product fit."""

    SEED_COMPANIES: ClassVar[list[tuple[str, str]]] = [
        ("Stripe", "https://stripe.com"),
        ("Twilio", "https://www.twilio.com"),
        ("Supabase", "https://supabase.com"),
        ("Vercel", "https://vercel.com"),
        ("MongoDB", "https://www.mongodb.com"),
        ("Auth0", "https://auth0.com"),
        ("Cloudflare", "https://www.cloudflare.com"),
        ("Postman", "https://www.postman.com"),
        ("Neon", "https://neon.tech"),
        ("Railway", "https://railway.app"),
        ("Render", "https://render.com"),
        ("Pinecone", "https://www.pinecone.io"),
    ]

    def get_source_type(self) -> DiscoverySource:
        return DiscoverySource.PRODUCT_LAUNCH

    def fetch_candidates(self) -> list[RawLead]:
        logger.info("Using %s seeded developer-product leads", len(self.SEED_COMPANIES))
        return [
            RawLead(
                name=name,
                website=website,
                source=DiscoverySource.PRODUCT_LAUNCH,
                notes="Developer platform with API/SDK hackathon potential",
            )
            for name, website in self.SEED_COMPANIES
        ]


def _extract_sponsor_section(html: str) -> str:
    lowered = html.lower()
    for marker in ("sponsor", "partners", "supported by", "our sponsors"):
        idx = lowered.find(marker)
        if idx != -1:
            return strip_html(html[max(0, idx - 200) : idx + 4000])
    return strip_html(html, max_chars=6000)


def _guess_company_names(text: str) -> list[str]:
    candidates = re.findall(
        r"\b([A-Z][A-Za-z0-9&.+]{1,30}(?:\s[A-Z][A-Za-z0-9&.+]{1,20}){0,2})\b", text
    )
    blocked = {
        "Hack Canada",
        "Major League",
        "Local Hack",
        "Devpost",
        "GitHub",
        "Google",
        "Microsoft",
        "Register",
        "Schedule",
        "Sponsors",
        "Partners",
    }
    results: list[str] = []
    for name in candidates:
        if name in blocked or len(name) < 3:
            continue
        if name not in results:
            results.append(name)
    return results[:40]
