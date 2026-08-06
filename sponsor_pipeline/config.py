"""
Settings management for the sponsor research pipeline.
Reads configuration from a .env file and exposes typed, validated values to the rest of the pipeline
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Supported AI LLM providers
SUPPORTED_PROVIDERS = ("anthropic", "openai", "google")


@dataclass
class Settings:
    """
    Centralized, typed configuration for the entire pipeline from environment variables defined in .env
    Used by LLMClient, WebScraperService, SponsorScoringService, PipelineOrchestrator, and SponsorRepository.
    """

    # AI LLM provider selection
    llm_provider: str
    anthropic_api_key: str
    openai_api_key: str
    google_api_key: str
    llm_model: str

    # Pipeline paths
    sponsor_db_path: Path
    hackathon_urls_file: Path
    scrape_log_path: Path

    # Pipeline settings
    min_overall_score: float
    max_crawl_pages: int
    max_emails_per_site: int
    mlh_events_url: str

    # Email generator settings
    sender_name: str
    sender_title: str
    event_name: str
    event_date: str
    event_venue: str

    @classmethod
    def from_env(cls, *, require_llm: bool = True) -> Settings:
        """
        Load settings from a .env file in the project root.

        Args:
            require_llm: if True (default), raises ValueError when the selected LLM provider's API key is missing.
                Set to False for scraper-only runs that don't need the LLM.

        Raises:
            ValueError: if the selected LLM provider is unsupported, or if require_llm=True and its API key is not set.
        """
        load_dotenv()
        project_root = Path(__file__).resolve().parent.parent

        # Determine which llm provider to use
        provider = os.getenv("LLM_PROVIDER", "anthropic").lower().strip()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"LLM_PROVIDER '{provider}' is not supported. "
                f"Choose one of: {', '.join(SUPPORTED_PROVIDERS)}"
            )

        # Read all API keys but only the active provider's key is required
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        openai_key = os.getenv("OPENAI_API_KEY", "")
        google_key = os.getenv("GOOGLE_API_KEY", "")

        if require_llm:
            active_key = {
                "anthropic": anthropic_key,
                "openai": openai_key,
                "google": google_key,
            }[provider]

            if not active_key or active_key == "your-key-here":
                raise ValueError(
                    f"API key for llm provider '{provider}' is not set. "
                    f"Copy env.example to .env and fill in the key."
                )

        # Default model per llm provider if LLM_MODEL not set
        default_models = {
            "anthropic": "claude-sonnet-4-6",
            "openai": "gpt-4o-mini",
            "google": "gemini-2.0-flash",
        }
        llm_model = os.getenv("LLM_MODEL") or default_models[provider]

        return cls(
            llm_provider=provider,
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
            google_api_key=google_key,
            llm_model=llm_model,
            sponsor_db_path=Path(
                os.getenv("SPONSOR_DB_PATH", str(project_root / "data" / "sponsors.db"))
            ),
            hackathon_urls_file=Path(
                os.getenv(
                    "HACKATHON_URLS_FILE",
                    str(project_root / "data" / "hackathon_urls.txt"),
                )
            ),
            scrape_log_path=Path(
                os.getenv("SCRAPE_LOG_PATH", str(project_root / "log.txt"))
            ),
            min_overall_score=float(os.getenv("MIN_OVERALL_SCORE", "6.0")),
            max_crawl_pages=int(os.getenv("MAX_CRAWL_PAGES", "50")),
            max_emails_per_site=int(os.getenv("MAX_EMAILS_PER_SITE", "5")),
            mlh_events_url=os.getenv(
                "MLH_EVENTS_URL", "https://www.mlh.io/seasons/2026/events"
            ),
            sender_name=os.getenv("SENDER_NAME", "Your Name Here"),
            sender_title=os.getenv("SENDER_TITLE", "Your Title Here"),
            event_name=os.getenv("EVENT_NAME", "ConUHacks X"),
            event_date=os.getenv("EVENT_DATE", "January 24-25, 2026"),
            event_venue=os.getenv(
                "EVENT_VENUE", "Concordia University's John Molson Building"
            ),
        )
