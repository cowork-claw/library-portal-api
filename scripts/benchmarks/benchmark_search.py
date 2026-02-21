"""
Benchmark for search performance using real paper data.

Uses the actual DataLoader to load real papers from the organized
data directory, ensuring benchmarks reflect production conditions.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app_v2.data_loader import DataLoader
from app_v2.services.indexing import PaperIndex
from app_v2.services.search import search_papers
from config.config_v2 import settings


def benchmark():
    # Load real data
    print("Loading real paper data...")
    loader = DataLoader(settings.DATA_DIRECTORY)
    index = PaperIndex()
    index.load_from_directory(loader)

    papers = index.papers
    print(f"Loaded {len(papers)} papers from {index.files_loaded} files")

    # Use a realistic search query
    query = "Algorithms"

    print(f"Benchmarking search on {len(papers)} papers...")

    # Warmup
    search_papers(papers[:100], query)

    # Benchmark
    start_time = time.perf_counter()
    iterations = 50
    for _ in range(iterations):
        search_papers(papers, query)
    end_time = time.perf_counter()

    avg_time = (end_time - start_time) / iterations
    print(f"Average search time over {iterations} iterations: {avg_time:.4f} seconds")


if __name__ == "__main__":
    benchmark()
