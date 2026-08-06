from __future__ import annotations

import argparse
import sys
from pathlib import Path

import sponsor_pipeline as pkg
from sponsor_pipeline.config import Settings
from sponsor_pipeline.logger import get_logger
from sponsor_pipeline.models import DiscoverySource
from sponsor_pipeline.orchestrator import PipelineOrchestrator

logger = get_logger(__name__)


# commands that indicate LLM access
LLM_COMMANDS = {"run", "discover", "score", "research", "contacts"}


def _looks_like_api_key(key: str) -> bool:
    # heuristic: non-empty, no whitespace, mostly alphanumeric, reasonable length
    if not key:
        return False
    k = key.strip()
    if not k:
        return False
    # no whitespace
    if any(c.isspace() for c in k):
        return False
    # reject obvious placeholder patterns or masked values
    low = k.lower()
    if "*" in k or "your-" in low or "replace" in low or "paste" in low or "changeme" in low:
        return False
    # require some alphanumeric content and no weird punctuation
    if not any(c.isalnum() for c in k):
        return False
    # reasonable minimal length to avoid placeholders
    return len(k) >= 16


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hack Canada sponsor research pipeline — discover, score, research, and find contacts."
    )
    # Add a global `--version` flag that prints the package release/version and exits.
    # This uses the `__release__` defined in `sponsor_pipeline/__init__.py`.
    parser.add_argument(
        "--version",
        action="version",
        version=pkg.__release__,
        help="Show program version and exit",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the full pipeline")
    run.add_argument(
        "--source",
        action="append",
        choices=[s.value for s in DiscoverySource],
        help="Limit discovery to specific source(s). Repeatable.",
    )

    sub.add_parser("discover", help="Part 1: discover companies")
    sub.add_parser("score", help="Part 2: score discovered companies")
    sub.add_parser("research", help="Part 3: research high-scoring companies")
    sub.add_parser("contacts", help="Part 4: find contacts for researched companies")

    export = sub.add_parser(
        "export", help="Export outreach-ready prospects to CSV/Markdown"
    )
    export.add_argument(
        "--output",
        default="data/exports",
        help="Output directory (default: data/exports)",
    )

    scrape = sub.add_parser("scrape", help="Scrape public emails from URLs")
    scrape.add_argument(
        "urls_file",
        nargs="?",
        default="urls.txt",
        help="Text file with one URL per line (batch mode; default: urls.txt)",
    )
    scrape.add_argument(
        "--url",
        help="Scrape a single URL directly (does not read or modify urls.txt)",
    )
    scrape.add_argument(
        "--output", default="emails.txt", help="Output file (default: emails.txt)"
    )
    scrape.add_argument(
        "--append",
        action="store_true",
        help="Append results to the output file instead of overwriting",
    )

    return parser


def _parse_sources(raw: list[str] | None) -> list[DiscoverySource] | None:
    if not raw:
        return None
    return [DiscoverySource(value) for value in raw]


def _run_scrape(args: argparse.Namespace, settings: Settings) -> int:
    from sponsor_pipeline.services.scraper import WebScraperService

    if args.url:
        urls = [args.url.strip()]
    else:
        urls_path = Path(args.urls_file)
        if not urls_path.exists():
            print(f"File not found: {urls_path}", file=sys.stderr)
            return 1
        urls = [
            line.strip()
            for line in urls_path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    if not urls:
        logger.error("No URLs to scrape.")
        return 1

    logger.info("Starting scrape for %s URL(s)", len(urls))
    scraper = WebScraperService(settings)
    lines: list[str] = []
    for index, url in enumerate(urls, start=1):
        logger.info("Scraping %s/%s: %s", index, len(urls), url)
        result = scraper.crawl_site(url)
        logger.info(
            "Scrape result for %s: %s page(s), %s email(s)",
            result.start_url,
            result.pages_crawled,
            len(result.emails),
        )
        lines.append(f"Website: {result.start_url}")
        lines.extend(result.emails)
        lines.append("")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines)
    if args.append and output_path.exists():
        existing = output_path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        text = existing + text
    output_path.write_text(text, encoding="utf-8")
    logger.info("Wrote scrape output to %s", output_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logger.info("Command selected: %s", args.command)
    try:
        settings = Settings.from_env(require_llm=args.command != "scrape")
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return 1
    logger.info(
        "Loaded settings: db=%s, provider=%s",
        settings.sponsor_db_path,
        settings.llm_provider,
    )

    # If this command will use the LLM, run a simple heuristic check on the active provider key.
    if args.command in LLM_COMMANDS:
        provider = settings.llm_provider
        env_name = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }.get(provider)
        key_val = getattr(settings, f"{provider}_api_key", "")
        if not _looks_like_api_key(key_val):
            logger.error(
                "Configuration error: API key for llm provider '%s' appears missing or malformed. Check %s in your .env",
                provider,
                env_name,
            )
            return 1

    if args.command == "scrape":
        return _run_scrape(args, settings)

    try:
        logger.info("Initializing pipeline orchestrator")
        orchestrator = PipelineOrchestrator(settings)
    except ValueError as exc:
        logger.error("Error: %s", exc)
        return 1
# wrapped everything in a try block.
    try:
        if args.command == "run":
            logger.info("Running full pipeline")
            result = orchestrator.run_full_pipeline(_parse_sources(args.source))
            logger.info("Pipeline complete")
            print("Pipeline complete:")
            for key, value in result.to_dict().items():
                print(f"  {key}: {value}")
            export_dir = settings.sponsor_db_path.parent / "exports"
            orchestrator.export_reports(export_dir)
            logger.info("Exports written to %s", export_dir)
        elif args.command == "discover":
            logger.info("Running discovery")
            companies = orchestrator.run_discovery()
            logger.info("Discovered %s companies", len(companies))
        elif args.command == "score":
            logger.info("Running scoring")
            companies = orchestrator.run_scoring()
            logger.info("Scored %s companies", len(companies))
        elif args.command == "research":
            logger.info("Running research")
            companies = orchestrator.run_research()
            logger.info("Researched %s companies", len(companies))
        elif args.command == "contacts":
            logger.info("Running contact discovery")
            prospects = orchestrator.run_contact_discovery()
            logger.info("Found contacts for %s companies", len(prospects))
        elif args.command == "export":
            orchestrator.export_reports(args.output)
            logger.info("Exported reports to %s", args.output)
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
