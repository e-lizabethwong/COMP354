"""
Tests for crawl_to_evidence in bridge.py
verifies that every field of CrawlResult lands in the right Evidence bucket
and that deduplication works — no API key required
"""

from __future__ import annotations

from sponsor_pipeline.models import (
    ContactMethod,
    ContactMethodType,
    CrawlResult,
    Evidence,
    EvidenceCategory,
)
from sponsor_pipeline.services.sponsor_evaluator.bridge import crawl_to_evidence


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _evidence(category: EvidenceCategory, description: str) -> Evidence:
    return Evidence(category=category, description=description, source_url="https://example.com")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_crawl_returns_empty_evidence():
    ev = crawl_to_evidence(CrawlResult(start_url="https://example.com"))
    assert ev.hiring_signals == []
    assert ev.developer_products == []
    assert ev.past_sponsorships == []
    assert ev.contact_signals == []
    assert ev.company_size_signals == []
    assert ev.canada_signals == []


def test_hiring_signal_goes_to_hiring_signals():
    crawl = CrawlResult(
        start_url="https://example.com",
        evidence=[_evidence(EvidenceCategory.HIRING_SIGNAL, "Hiring interns in Waterloo")],
    )
    ev = crawl_to_evidence(crawl)
    assert any("Hiring interns in Waterloo" in s for s in ev.hiring_signals)


def test_developer_product_goes_to_developer_products():
    crawl = CrawlResult(
        start_url="https://example.com",
        evidence=[_evidence(EvidenceCategory.DEVELOPER_PRODUCT_FIT, "Public REST API")],
    )
    ev = crawl_to_evidence(crawl)
    assert any("Public REST API" in s for s in ev.developer_products)


def test_past_sponsorship_goes_to_past_sponsorships():
    crawl = CrawlResult(
        start_url="https://example.com",
        evidence=[_evidence(EvidenceCategory.PAST_SPONSORSHIP, "Sponsored HackTheNorth 2024")],
    )
    ev = crawl_to_evidence(crawl)
    assert any("Sponsored HackTheNorth 2024" in s for s in ev.past_sponsorships)


def test_contactability_goes_to_contact_signals():
    crawl = CrawlResult(
        start_url="https://example.com",
        evidence=[_evidence(EvidenceCategory.CONTACTABILITY, "DevRel manager on LinkedIn")],
    )
    ev = crawl_to_evidence(crawl)
    assert any("DevRel manager on LinkedIn" in s for s in ev.contact_signals)


def test_canada_fit_goes_to_canada_signals():
    crawl = CrawlResult(
        start_url="https://example.com",
        evidence=[_evidence(EvidenceCategory.WATERLOO_CANADA_FIT, "Toronto office")],
    )
    ev = crawl_to_evidence(crawl)
    assert any("Toronto office" in s for s in ev.canada_signals)


def test_emails_go_to_contact_signals():
    crawl = CrawlResult(
        start_url="https://example.com",
        emails=["partnerships@acme.com"],
    )
    ev = crawl_to_evidence(crawl)
    assert any("partnerships@acme.com" in s for s in ev.contact_signals)


def test_social_links_go_to_contact_signals():
    crawl = CrawlResult(
        start_url="https://example.com",
        social_links=[
            ContactMethod(
                type=ContactMethodType.LINKEDIN,
                value="linkedin.com/in/devrel",
                source_url="https://example.com",
            )
        ],
    )
    ev = crawl_to_evidence(crawl)
    assert any("linkedin.com/in/devrel" in s for s in ev.contact_signals)


def test_funding_keyword_in_snippet_goes_to_size_signals():
    crawl = CrawlResult(
        start_url="https://example.com",
        page_snippets={"https://example.com/about": "Series B startup with 150 employees"},
    )
    ev = crawl_to_evidence(crawl)
    assert any("Series B" in s for s in ev.company_size_signals)


def test_about_page_url_goes_to_contact_signals():
    crawl = CrawlResult(
        start_url="https://example.com",
        page_snippets={"https://example.com/about": "Meet the team"},
    )
    ev = crawl_to_evidence(crawl)
    assert any("about" in s.lower() for s in ev.contact_signals)


def test_duplicate_signals_are_deduped():
    # the same email added twice should appear only once in contact_signals
    crawl = CrawlResult(
        start_url="https://example.com",
        emails=["dup@acme.com", "dup@acme.com"],
    )
    ev = crawl_to_evidence(crawl)
    matching = [s for s in ev.contact_signals if "dup@acme.com" in s]
    assert len(matching) == 1
