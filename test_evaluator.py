"""
Quick smoke test for the sponsor evaluator module.
Bypasses the scraper and full pipeline, feeds fake evidence directly
into the evaluator so you can verify the LLM calls and structured output
work correctly without waiting 2 hours for a full run

Reads LLM_PROVIDER from .env

Run with:
    python3 test_evaluator.py
"""

from sponsor_pipeline.config import Settings
from sponsor_pipeline.orchestrator import _build_dimension_evaluator
from sponsor_pipeline.services.sponsor_evaluator import SponsorEvaluator
from sponsor_pipeline.services.sponsor_evaluator.schemas import Company, Evidence

# --- Fake company and evidence (no scraping needed) ---
company = Company(
    name="Shopify",
    website="https://shopify.com",
    industry="E-commerce / Developer Tools",
    description="Canadian e-commerce platform with a large developer ecosystem.",
)

evidence = Evidence(
    hiring_signals=[
        "Actively hiring software engineers in Ottawa and Toronto",
        "Campus recruiter listed on LinkedIn targeting Waterloo students",
    ],
    developer_products=[
        "Public REST and GraphQL APIs with free sandbox tier",
        "Open-source Polaris design system on GitHub",
    ],
    past_sponsorships=[
        "Sponsor at HackTheNorth 2023",
        "Listed as MLH partner",
    ],
    contact_signals=[
        "devrel@shopify.com listed on developer portal",
        "Developer Relations team active on Twitter",
    ],
    company_size_signals=[
        "~10,000 employees, publicly traded (TSX/NYSE)",
        "Significant engineering budget",
    ],
    canada_signals=[
        "Headquartered in Ottawa, Canada",
        "Strong Waterloo co-op hiring program",
    ],
)

# --- Load settings from .env and run the evaluator ---
# The factory reads LLM_PROVIDER from .env and picks the right evaluator automatically
# To switch providers, just change LLM_PROVIDER in .env
settings = Settings.from_env()
evaluator = SponsorEvaluator(_build_dimension_evaluator(settings))

print(f"Evaluating: {company.name} (provider: {settings.llm_provider})")
print("This makes 7 LLM calls (6 dimensions + 1 summary) — takes ~30 seconds...\n")

score = evaluator.evaluate(company, evidence)

# --- Print results ---
print(f"Overall score: {score.overall_score:.2f} / 10")
print(f"Confidence:    {score.confidence.value}")
print(f"Motivations:   {[m.value for m in score.motivations]}")
print(f"\nExplanation:\n{score.explanation}")
print("\nKey strengths:")
for s in score.key_strengths:
    print(f"  - {s}")
print("\nPotential weaknesses:")
for w in score.potential_weaknesses:
    print(f"  - {w}")
print(f"\nOutreach angle: {score.recommended_outreach_angle}")
print(f"Contact role:   {score.recommended_contact_role}")
print("\nDimension scores:")
for key, cs in score.criterion_scores.items():
    print(f"  {key}: {cs.score}/10 — {cs.reasoning}")
