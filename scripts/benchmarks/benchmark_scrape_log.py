"""
Benchmark for ScrapeLog operations using real scraped URLs.

Measures add_scraped_url, has_url, and duplicate-add performance
against URLs from the actual organized data files.
"""

import sys
import time
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scraper.scrape_log import ScrapeLog, load_existing_urls_from_organized_data
from config.config_v2 import settings


def _load_real_urls(target_count: int = 10000) -> list[str]:
    """Load real URLs from organized data, padding with realistic synthetics if needed."""
    real_urls = list(load_existing_urls_from_organized_data(settings.DATA_DIRECTORY))
    print(f"Loaded {len(real_urls)} real URLs from organized data")

    if len(real_urls) >= target_count:
        return real_urls[:target_count]

    # Pad with realistic synthetic URLs based on real URL patterns
    base = "https://libportal.manipal.edu/RootFolder"
    semesters = ["I Sem", "II Sem", "III Sem", "IV Sem", "V Sem", "VI Sem"]
    years = ["2022", "2023", "2024", "2025"]
    padded = list(real_urls)
    i = 0
    while len(padded) < target_count:
        sem = semesters[i % len(semesters)]
        yr = years[i % len(years)]
        padded.append(
            f"{base}/{yr}/Dec%20{yr}/{sem}/Computer%20Science%20and%20Engineering"
            f"/Benchmark%20Paper%20%28CSE%20{10000+i}%29.pdf"
        )
        i += 1

    return padded


def benchmark_scrape_log():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "scrape_log.json"
        scrape_log = ScrapeLog(log_file)

        urls = _load_real_urls(10000)
        num_urls = len(urls)

        # Benchmark add_scraped_url
        start_time = time.perf_counter()
        for url in urls:
            scrape_log.add_scraped_url(url)
        end_time = time.perf_counter()

        print(f"Added {num_urls} unique URLs in {end_time - start_time:.4f} seconds")

        # Benchmark has_url
        start_time = time.perf_counter()
        for url in urls:
            scrape_log.has_url(url)
        end_time = time.perf_counter()

        print(f"Checked {num_urls} existing URLs in {end_time - start_time:.4f} seconds")

        # Benchmark add_scraped_url with existing URLs
        start_time = time.perf_counter()
        for url in urls:
            scrape_log.add_scraped_url(url)
        end_time = time.perf_counter()

        print(f"Attempted to add {num_urls} existing URLs in {end_time - start_time:.4f} seconds")


if __name__ == "__main__":
    benchmark_scrape_log()
