import tempfile
import time
from pathlib import Path

from scraper.scrape_log import ScrapeLog, _load_existing_urls_from_organized_data


def benchmark_scrape_log():
    # Load real URLs from the data directory
    data_dir = Path("data/classified/organized")
    real_urls = list(_load_existing_urls_from_organized_data(data_dir))

    print(f"Found {len(real_urls)} real URLs in data directory.")

    # If we have too few, supplement them with variants to get to 10,000
    urls = real_urls.copy()
    if len(urls) < 10000:
        needed = 10000 - len(urls)
        print(
            f"Supplementing with {needed} variants to reach 10,000 for meaningful benchmark."
        )
        base_url = (
            urls[0] if urls else "https://libportal.manipal.edu/RootFolder/Paper.pdf"
        )
        for i in range(needed):
            urls.append(f"{base_url}?v={i}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        log_file = Path(tmp_dir) / "scrape_log.json"
        scrape_log = ScrapeLog(log_file)

        # Benchmark add_scraped_url
        start_time = time.perf_counter()
        for url in urls:
            scrape_log.add_scraped_url(url)
        end_time = time.perf_counter()

        print(f"Added {len(urls)} URLs in {end_time - start_time:.4f} seconds")

        # Benchmark has_url
        start_time = time.perf_counter()
        for url in urls:
            scrape_log.has_url(url)
        end_time = time.perf_counter()

        print(
            f"Checked {len(urls)} existing URLs in {end_time - start_time:.4f} seconds"
        )

        # Benchmark add_scraped_url with existing URLs
        start_time = time.perf_counter()
        for url in urls:
            scrape_log.add_scraped_url(url)
        end_time = time.perf_counter()

        print(
            f"Attempted to add {len(urls)} existing URLs in {end_time - start_time:.4f} seconds"
        )


if __name__ == "__main__":
    benchmark_scrape_log()
