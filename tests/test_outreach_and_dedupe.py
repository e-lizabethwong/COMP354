import unittest
from pathlib import Path
import tempfile

from sponsor_pipeline.config import Settings
from sponsor_pipeline.models import Company, DiscoverySource, LeadStatus
from sponsor_pipeline.prompts.templates import PromptTemplateRegistry
from sponsor_pipeline.services.discovery import _dedupe_companies, _normalize_name, _is_fuzzy_match
from sponsor_pipeline.services.outreach import OutreachService
from sponsor_pipeline.persistence.repository import SponsorRepository


class TestOutreachAndDedupe(unittest.TestCase):

    def test_dynamic_event_prompts(self):
        prompts = PromptTemplateRegistry(event_name="ConUHacks X")
        discovery_p = prompts.get_discovery_prompt()
        scoring_p = prompts.get_scoring_prompt()
        research_p = prompts.get_research_prompt()

        self.assertIn("ConUHacks X", discovery_p)
        self.assertIn("ConUHacks X", scoring_p)
        self.assertIn("ConUHacks X", research_p)
        self.assertNotIn("Hack Canada", discovery_p)

    def test_company_name_normalization(self):
        self.assertEqual(_normalize_name("Shopify Inc."), "shopify")
        self.assertEqual(_normalize_name("Shopify Canada"), "shopify")
        self.assertEqual(_normalize_name("Stripe LLC"), "stripe")

    def test_fuzzy_matching(self):
        self.assertTrue(_is_fuzzy_match("Shopify", "Shopify Inc."))
        self.assertTrue(_is_fuzzy_match("Shopify Canada", "Shopify"))

    def test_dedupe_companies(self):
        leads = [
            Company(name="Shopify", website="https://shopify.com", discovery_sources=[DiscoverySource.MLH_EVENT]),
            Company(name="Shopify Inc.", website="https://shopify.com", discovery_sources=[DiscoverySource.JOB_POSTING]),
            Company(name="Shopify Canada", website="", discovery_sources=[DiscoverySource.MANUAL_INPUT]),
            Company(name="Stripe", website="https://stripe.com", discovery_sources=[DiscoverySource.PRODUCT_LAUNCH]),
        ]
        deduped = _dedupe_companies(leads)
        self.assertEqual(len(deduped), 2)
        names = [c.name for c in deduped]
        self.assertIn("Shopify", names)
        self.assertIn("Stripe", names)

    def test_outreach_service(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = SponsorRepository(db_path)
            settings = Settings.from_env(require_llm=False)
            settings.event_name = "ConUHacks X"
            settings.sender_name = "Alex Wong"
            settings.sender_title = "Director"

            outreach = OutreachService(settings, repo)
            subject, body = outreach.generate_initial_email("Shopify", "Jane Doe", is_local=True)

            self.assertIn("Shopify", subject)
            self.assertIn("ConUHacks X", subject)
            self.assertIn("Jane Doe", body)
            self.assertIn("Alex Wong", body)


if __name__ == "__main__":
    unittest.main()
