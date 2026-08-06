from __future__ import annotations

import asyncio
import re
from collections import deque
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright
from playwright.sync_api import Error, TimeoutError, sync_playwright

from sponsor_pipeline.config import Settings
from sponsor_pipeline.logger import get_logger
from sponsor_pipeline.models import (
    ContactMethod,
    ContactMethodType,
    CrawlResult,
    Evidence,
    EvidenceCategory,
)

logger = get_logger(__name__)

SKIP_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".mp4",
    ".mp3",
    ".css",
    ".js",
    ".ico",
    ".woff",
    ".woff2",
)
PRIORITY_KEYWORDS = (
    "contact",
    "about",
    "team",
    "career",
    "jobs",
    "people",
    "sponsor",
    "partners",
    "community",
    "devrel",
    "blog",
)
EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", re.IGNORECASE
)
LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[A-Za-z0-9_/%-]+", re.IGNORECASE
)
TWITTER_RE = re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+", re.IGNORECASE)
GITHUB_RE = re.compile(r"https?://(?:www\.)?github\.com/[A-Za-z0-9_-]+", re.IGNORECASE)


class WebScraperService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._log_path = settings.scrape_log_path

    def crawl_site(self, start_url: str) -> CrawlResult:
        start_url = normalize_url(start_url)
        visited: set[str] = set()
        emails: set[str] = set()
        social: dict[str, ContactMethod] = {}
        snippets: dict[str, str] = {}
        evidence: list[Evidence] = []
        queue = deque(_prioritize_links([start_url], start_url))
        pages_crawled = 0

        self._log(f"Starting crawl: {start_url}")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )
            try:
                while queue and pages_crawled < self._settings.max_crawl_pages:
                    if (
                        len(emails) >= self._settings.max_emails_per_site
                        and pages_crawled > 10
                    ):
                        self._log(
                            "Stopping crawl after finding enough emails: "
                            f"{len(emails)} email(s)"
                        )
                        break

                    url = queue.popleft()
                    if url in visited:
                        continue
                    visited.add(url)

                    html = self._fetch_page(context, url)
                    if not html:
                        self._log(f"Failed to crawl: {url}")
                        continue

                    pages_crawled += 1
                    self._log(f"Crawled: {url}")
                    snippets[url] = _html_to_text(html, 2500)

                    for email in _extract_emails(html):
                        if email not in emails:
                            emails.add(email)
                            self._log(f"Found email: {email} on {url}")
                            evidence.append(
                                Evidence(
                                    category=EvidenceCategory.CONTACTABILITY,
                                    description=f"Public email found: {email}",
                                    source_url=url,
                                )
                            )

                    for method in _extract_social_links(html, url):
                        social[method.value] = method

                    for link in _get_internal_links(html, start_url):
                        if link not in visited and link not in queue:
                            if _is_priority_link(link):
                                queue.appendleft(link)
                            else:
                                queue.append(link)

                    _collect_evidence(html, url, evidence)
            finally:
                context.close()
                browser.close()

        result = CrawlResult(
            start_url=start_url,
            pages_crawled=pages_crawled,
            emails=sorted(emails),
            social_links=list(social.values()),
            page_snippets=snippets,
            evidence=evidence,
        )
        self._log(
            f"Finished crawl: {start_url} ({pages_crawled} pages, {len(emails)} emails)"
        )
        return result

    def batch_crawl(self, urls: list[str], use_async: bool = False) -> list[CrawlResult]:
        """Crawl a list of URLs sequentially or concurrently.

        Args:
            urls: list of starting URLs to crawl.
            use_async: when True, crawl all URLs concurrently using
                asyncio and playwright's async API. Defaults to False
                for backwards compatibility.
        """
        logger.info("Starting batch crawl for %s URL(s) (async=%s)", len(urls), use_async)
        if use_async:
            return asyncio.run(self._batch_crawl_async(urls))
        return [self.crawl_site(url) for url in urls]

    async def _crawl_site_async(self, start_url: str, context) -> CrawlResult:
        """Async equivalent of crawl_site(). Uses a shared browser context."""
        start_url = normalize_url(start_url)
        visited: set[str] = set()
        emails: set[str] = set()
        social: dict[str, ContactMethod] = {}
        snippets: dict[str, str] = {}
        evidence: list[Evidence] = []
        queue = deque(_prioritize_links([start_url], start_url))
        pages_crawled = 0

        self._log(f"Starting async crawl: {start_url}")

        while queue and pages_crawled < self._settings.max_crawl_pages:
            if len(emails) >= self._settings.max_emails_per_site and pages_crawled > 10:
                self._log(f"Stopping crawl after finding enough emails: {len(emails)} email(s)")
                break

            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            html = await self._fetch_page_async(context, url)
            if not html:
                self._log(f"Failed to crawl: {url}")
                continue

            pages_crawled += 1
            self._log(f"Crawled: {url}")
            snippets[url] = _html_to_text(html, 2500)

            for email in _extract_emails(html):
                if email not in emails:
                    emails.add(email)
                    self._log(f"Found email: {email} on {url}")
                    evidence.append(
                        Evidence(
                            category=EvidenceCategory.CONTACTABILITY,
                            description=f"Public email found: {email}",
                            source_url=url,
                        )
                    )

            for method in _extract_social_links(html, url):
                social[method.value] = method

            for link in _get_internal_links(html, start_url):
                if link not in visited and link not in queue:
                    if _is_priority_link(link):
                        queue.appendleft(link)
                    else:
                        queue.append(link)

            _collect_evidence(html, url, evidence)

        result = CrawlResult(
            start_url=start_url,
            pages_crawled=pages_crawled,
            emails=sorted(emails),
            social_links=list(social.values()),
            page_snippets=snippets,
            evidence=evidence,
        )
        self._log(f"Finished async crawl: {start_url} ({pages_crawled} pages, {len(emails)} emails)")
        return result

    async def _batch_crawl_async(self, urls: list[str]) -> list[CrawlResult]:
        """Launch a shared browser and crawl all URLs concurrently.

        A semaphore caps the number of sites being crawled at the same
        time so we don't overwhelm the machine or the target servers.
        """
        logger.info("Starting async batch crawl for %s URL(s)", len(urls))

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )

            semaphore = asyncio.Semaphore(10)

            async def _bounded(url: str) -> CrawlResult:
                async with semaphore:
                    return await self._crawl_site_async(url, context)

            results = await asyncio.gather(*[_bounded(u) for u in urls])

            await context.close()
            await browser.close()

            return results

    @staticmethod
    def _fetch_page(context, url: str) -> str:
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(1000)
            return page.content()
        except (TimeoutError, Error) as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            return ""
        finally:
            page.close()

    @staticmethod
    async def _fetch_page_async(context, url: str) -> str:
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(1000)
            return await page.content()
        except (Error, TimeoutError) as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            return ""
        finally:
            await page.close()

    def _log(self, message: str) -> None:
        logger.info(message)
        if self._log_path:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(message + "\n")


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return url


def _same_domain(url: str, base_url: str) -> bool:
    base = urlparse(base_url).netloc.replace("www.", "")
    host = urlparse(url).netloc.replace("www.", "")
    return host == base or host.endswith("." + base) or base.endswith("." + host)


def _get_internal_links(html: str, base_url: str) -> list[str]:
    href_pattern = re.compile(r'href=["\'](.*?)["\']', re.IGNORECASE)
    internal: list[str] = []
    for link in href_pattern.findall(html):
        absolute = urljoin(base_url, link)
        parsed = urlparse(absolute)
        if parsed.path.lower().endswith(SKIP_EXTENSIONS):
            continue
        if _same_domain(absolute, base_url):
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if clean not in internal:
                internal.append(clean)
    return internal


def _prioritize_links(links: list[str], base_url: str) -> list[str]:
    priority = [link for link in links if _is_priority_link(link)]
    rest = [link for link in links if link not in priority]
    return priority + rest


def _is_priority_link(url: str) -> bool:
    lower = url.lower()
    return any(keyword in lower for keyword in PRIORITY_KEYWORDS)


def _extract_emails(html: str) -> list[str]:
    valid: list[str] = []
    for email in EMAIL_RE.findall(html):
        lower = email.lower()
        if any(ext in lower for ext in (".js", ".css", ".min.", ".bundle", ".png")):
            continue
        if re.search(r"@\d+(\.\d+)*", email):
            continue
        local, domain = email.split("@", 1)
        if re.search(r"[a-zA-Z]", local) and "." in domain:
            valid.append(email)
    return valid


def _extract_social_links(html: str, source_url: str) -> list[ContactMethod]:
    methods: list[ContactMethod] = []
    for pattern, ctype in (
        (LINKEDIN_RE, ContactMethodType.LINKEDIN),
        (TWITTER_RE, ContactMethodType.X_TWITTER),
        (GITHUB_RE, ContactMethodType.GITHUB),
    ):
        for match in pattern.findall(html):
            methods.append(
                ContactMethod(
                    type=ctype, value=match, source_url=source_url, confidence=0.7
                )
            )
    return methods


def _html_to_text(html: str, max_chars: int) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _collect_evidence(html: str, url: str, evidence: list[Evidence]) -> None:
    text = _html_to_text(html, 5000).lower()
    if any(word in text for word in ("hackathon", "mlh", "devpost", "sponsor")):
        evidence.append(
            Evidence(
                category=EvidenceCategory.PAST_SPONSORSHIP,
                description="Page mentions hackathon/sponsorship activity",
                source_url=url,
            )
        )
    if any(
        city in text
        for city in ("waterloo", "toronto", "vancouver", "montreal", "canada")
    ):
        evidence.append(
            Evidence(
                category=EvidenceCategory.WATERLOO_CANADA_FIT,
                description="Page mentions Canadian city or Canada hiring",
                source_url=url,
            )
        )
    if any(
        word in text for word in ("api", "sdk", "developer", "documentation", "devrel")
    ):
        evidence.append(
            Evidence(
                category=EvidenceCategory.DEVELOPER_PRODUCT_FIT,
                description="Page mentions developer products or docs",
                source_url=url,
            )
        )
    if any(
        word in text
        for word in ("intern", "new grad", "co-op", "coop", "campus recruiter")
    ):
        evidence.append(
            Evidence(
                category=EvidenceCategory.HIRING_SIGNAL,
                description="Page mentions student hiring or campus recruiting",
                source_url=url,
            )
        )
