"""
Quick demo of SponsorEvaluator against a real company
runs a full evaluation and prints every field of the resulting SponsorScore
requires ANTHROPIC_API_KEY in .env
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the project root to sys.path so sponsor_pipeline resolves when the
# script is run directly from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

import anthropic
from dotenv import load_dotenv

from sponsor_pipeline.services.sponsor_evaluator.evaluator import SponsorEvaluator
from sponsor_pipeline.services.sponsor_evaluator.llm.sponsor_dimension_evaluator import (
    ClaudeSponsorDimensionEvaluator,
)
from sponsor_pipeline.services.sponsor_evaluator.schemas import Company, Evidence

load_dotenv()

# ---------------------------------------------------------------------------
# Sample company — Shopify (Canadian HQ, active hackathon sponsor, devrel team)
# ---------------------------------------------------------------------------

company = Company(
    name="Shopify",
    website="https://shopify.dev",
    industry="E-commerce / Developer Tools",
    description=(
        "Shopify is a Canadian e-commerce platform that provides APIs, SDKs, "
        "and a large developer ecosystem. Headquartered in Ottawa with offices "
        "across Canada. Known for aggressive campus recruiting and sponsoring "
        "major hackathons through their developer relations team."
    ),
)

evidence = Evidence(
    hiring_signals=[
        "Shopify Dev Degree co-op program for CS students",
        "Active campus recruiter postings on Waterloo WaterlooWorks",
        "Internship listings targeting Waterloo, UofT, McGill students",
        "New grad software engineer roles posted in Ottawa and Toronto",
    ],
    developer_products=[
        "Shopify API with extensive public documentation at shopify.dev",
        "Polaris design system open-sourced on GitHub",
        "Remix framework maintained by Shopify (open source)",
        "Shopify CLI and developer sandbox available for free",
        "Active developer Discord with 10k+ members",
    ],
    past_sponsorships=[
        "Title sponsor at Hack the North 2023",
        "Listed as sponsor on MLH 2024 season page",
        "Sponsored UofT Hacks and ConUHacks in previous years",
    ],
    contact_signals=[
        "Developer Relations team listed on shopify.dev/community",
        "devrel@shopify.com referenced in developer docs",
        "Director of Developer Experience active on X (@shopifydevs)",
        "University recruiting page at shopify.com/careers/university",
    ],
    company_size_signals=[
        "~10,000 employees as of 2024",
        "Publicly traded on NYSE and TSX (SHOP)",
        "Dedicated developer marketing and partnerships budget",
    ],
    canada_signals=[
        "Headquartered in Ottawa, Ontario",
        "Major offices in Toronto and Waterloo region",
        "Waterloo co-op program partner since 2013",
        "Active in Canadian startup and tech community",
    ],
)

# ---------------------------------------------------------------------------
# Run the evaluation
# ---------------------------------------------------------------------------

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
dimension_evaluator = ClaudeSponsorDimensionEvaluator(client)
evaluator = SponsorEvaluator(dimension_evaluator)

print(f"Evaluating {company.name}...\n")
result = evaluator.evaluate(company, evidence)

# ---------------------------------------------------------------------------
# Print the result
# ---------------------------------------------------------------------------

print("=" * 60)
print(f"  {result.company.name} — Overall Score: {result.overall_score}/10")
print("=" * 60)

print("\nCriterion Scores")
print("-" * 60)
for key, cs in result.criterion_scores.items():
    print(f"  {key:<30} {cs.score:>4.1f}/10")
    print(f"    {cs.reasoning}")
    if cs.supporting_evidence:
        for item in cs.supporting_evidence:
            print(f"      - {item}")
    print()

print("-" * 60)
print(f"  Confidence:          {result.confidence.value}")
print(f"  Motivations:         {', '.join(m.value for m in result.motivations)}")
print(f"  Outreach angle:      {result.recommended_outreach_angle}")
print(f"  Contact role:        {result.recommended_contact_role}")
print()
print("  Explanation")
print(f"  {result.explanation}")
print()
print("  Key strengths")
for s in result.key_strengths:
    print(f"    + {s}")
print()
print("  Potential weaknesses")
for w in result.potential_weaknesses:
    print(f"    - {w}")
print("=" * 60)
