import tempfile
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
        scrape_log.data["scraped_urls"] = urls
        scrape_log._scraped_urls_set = set(urls)

        start_time = time.perf_counter()
        scraped_urls = scrape_log._get_scraped_urls()
        end_time = time.perf_counter()

        print(f"Copied {len(scraped_urls)} URLs in {end_time - start_time:.4f} seconds")

        start_time = time.perf_counter()
        for url in urls:
            url in scraped_urls
        end_time = time.perf_counter()

        print(
            f"Checked {len(urls)} existing URLs in {end_time - start_time:.4f} seconds"
        )


if __name__ == "__main__":
    benchmark_scrape_log()
