import time
import tempfile
from pathlib import Path
from scraper.scrape_log import ScrapeLog

def benchmark_scrape_log():
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        log_file = Path(tmp.name)
        scrape_log = ScrapeLog(log_file)

        num_urls = 10000
        urls = [f"https://example.com/paper/{i}.pdf" for i in range(num_urls)]

        # Benchmark add_scraped_url
        start_time = time.time()
        for url in urls:
            scrape_log.add_scraped_url(url)
        end_time = time.time()

        print(f"Added {num_urls} unique URLs in {end_time - start_time:.4f} seconds")

        # Benchmark has_url
        start_time = time.time()
        for url in urls:
            scrape_log.has_url(url)
        end_time = time.time()

        print(f"Checked {num_urls} existing URLs in {end_time - start_time:.4f} seconds")

        # Benchmark add_scraped_url with existing URLs
        start_time = time.time()
        for url in urls:
            scrape_log.add_scraped_url(url)
        end_time = time.time()

        print(f"Attempted to add {num_urls} existing URLs in {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    benchmark_scrape_log()
