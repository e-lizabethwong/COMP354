"""
Benchmark: Synchronous vs Asynchronous Scraper Performance

Compare the execution time of batch_crawl() in synchronous mode
versus asynchronous mode across hackathon websites.

Usage:
    python benchmark_scraper.py
"""

import logging
import time

from sponsor_pipeline.config import Settings
from sponsor_pipeline.services.scraper import WebScraperService

# Small set of URLs for a baseline measurement
BASELINE_URLS = [
    "https://conuhacks.io",
    "https://mchacks.ca",
]

# Larger set to stress test
STRESS_TEST_URLS = [
    "https://conuhacks.io",
    "https://mchacks.ca",
    "https://hackthenorth.com",
    "https://canadahacks.ca",
    "https://vercel.com",
    "https://stripe.com",
    "https://www.jetbrains.com",
    "https://www.cloudflare.com",
]

# Scraper settings for the benchmark
MAX_PAGES_PER_SITE = 2
MAX_EMAILS_PER_SITE = 3


def _timed_crawl(scraper, urls, use_async):
    """Run a batch crawl and return the elapsed time in seconds."""
    start = time.time()
    scraper.batch_crawl(urls, use_async=use_async)
    return time.time() - start


def run_benchmark():
    """Run the full sync-vs-async benchmark and print a results table."""
    settings = Settings.from_env(require_llm=False)
    settings.max_crawl_pages = MAX_PAGES_PER_SITE
    settings.max_emails_per_site = MAX_EMAILS_PER_SITE

    # keep crawler warnings out of the benchmark output
    logging.getLogger("sponsor_pipeline.services.scraper").setLevel(logging.WARNING)

    scraper = WebScraperService(settings)

    print("Scraper Performance Benchmark")
    print(f"Pages per site: {MAX_PAGES_PER_SITE} | "
          f"Baseline URLs: {len(BASELINE_URLS)} | "
          f"Stress test URLs: {len(STRESS_TEST_URLS)}\n")

    # run the three tests
    print(f"[1/3] Baseline ({len(BASELINE_URLS)} URLs, sync)...")
    baseline_time = _timed_crawl(scraper, BASELINE_URLS, use_async=False)
    print(f"      done in {baseline_time:.2f}s\n")

    print(f"[2/3] Stress test ({len(STRESS_TEST_URLS)} URLs, sync)...")
    sync_time = _timed_crawl(scraper, STRESS_TEST_URLS, use_async=False)
    print(f"      done in {sync_time:.2f}s\n")

    print(f"[3/3] Stress test ({len(STRESS_TEST_URLS)} URLs, async)...")
    async_time = _timed_crawl(scraper, STRESS_TEST_URLS, use_async=True)
    print(f"      done in {async_time:.2f}s\n")

    # results table
    print("-" * 45)
    print(f"{'Test':<30} {'Time':>8}")
    print("-" * 45)
    print(f"{'Baseline (sync)':<30} {baseline_time:>7.2f}s")
    print(f"{'Stress test (sync)':<30} {sync_time:>7.2f}s")
    print(f"{'Stress test (async)':<30} {async_time:>7.2f}s")
    print("-" * 45)

    if sync_time > 0:
        speedup = ((sync_time - async_time) / sync_time) * 100
        print(f"Async is {speedup:.1f}% faster than sync.")
    print("-" * 45)


if __name__ == "__main__":
    run_benchmark()

