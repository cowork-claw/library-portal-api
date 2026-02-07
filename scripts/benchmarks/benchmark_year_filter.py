import statistics
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app_v2.data_loader import DataLoader
from app_v2.services.indexing import paper_index
from config.config_v2 import settings


def setup():
    print("Loading data...")
    loader = DataLoader(settings.DATA_DIRECTORY)
    paper_index.load_from_directory(loader)
    print(f"Loaded {paper_index.total_papers} papers.")


def current_implementation(year, semester):
    """Replicates the logic in app_v2/routes/papers.py before optimization"""
    urls = paper_index.get_urls_by_year(year)
    papers = paper_index.get_by_urls(urls)

    if not papers:
        # simulating the check, though we don't raise exception in benchmark
        return []

    if semester is not None:
        papers = [p for p in papers if p.get("semester") == semester]

    return papers


def optimized_implementation(year, semester):
    """Proposed optimized logic"""
    year_urls = paper_index.get_urls_by_year(year)

    if not year_urls:
        return []

    if semester is not None:
        semester_urls = paper_index.get_urls_by_semester(semester)
        intersected_urls = year_urls.intersection(semester_urls)
        papers = paper_index.get_by_urls(intersected_urls)
    else:
        papers = paper_index.get_by_urls(year_urls)

    return papers


def benchmark(year=2022, semester=5, iterations=1000):
    print(f"\nBenchmarking Year={year}, Semester={semester}, Iterations={iterations}")

    # Warmup
    current_implementation(year, semester)
    optimized_implementation(year, semester)

    # Measure Current
    times_current = []
    for _ in range(iterations):
        start = time.perf_counter()
        res_curr = current_implementation(year, semester)
        end = time.perf_counter()
        times_current.append((end - start) * 1000)  # ms

    # Measure Optimized
    times_opt = []
    for _ in range(iterations):
        start = time.perf_counter()
        res_opt = optimized_implementation(year, semester)
        end = time.perf_counter()
        times_opt.append((end - start) * 1000)  # ms

    # Verification
    res_curr = current_implementation(year, semester)
    res_opt = optimized_implementation(year, semester)
    print(f"Current result count: {len(res_curr)}")
    print(f"Optimized result count: {len(res_opt)}")

    if len(res_curr) != len(res_opt):
        print("⚠️  WARNING: Result counts differ!")

    # Verify content (checking IDs/URLs)
    curr_urls = sorted([p["url"] for p in res_curr])
    opt_urls = sorted([p["url"] for p in res_opt])
    if curr_urls != opt_urls:
        print("⚠️  WARNING: Result contents differ!")
    else:
        print("✅ Results match.")

    avg_curr = statistics.mean(times_current)
    avg_opt = statistics.mean(times_opt)
    if avg_curr > 0:
        improvement = ((avg_curr - avg_opt) / avg_curr) * 100
        speedup = avg_curr / avg_opt if avg_opt > 0 else 0
    else:
        improvement = 0
        speedup = 0

    print("\nResults:")
    print(f"Current Avg:   {avg_curr:.4f} ms")
    print(f"Optimized Avg: {avg_opt:.4f} ms")
    print(f"Improvement:   {improvement:.2f}%")
    print(f"Speedup:       {speedup:.2f}x")


if __name__ == "__main__":
    setup()

    # Find a good year/semester to test
    if paper_index.unique_years:
        test_year = paper_index.unique_years[0]
        # Find a semester that exists in this year
        urls = paper_index.get_urls_by_year(test_year)
        papers = paper_index.get_by_urls(urls)
        semesters = list(set(p.get("semester") for p in papers if p.get("semester")))

        if semesters:
            # Pick a semester with reasonable count
            test_sem = semesters[0]
            benchmark(year=test_year, semester=test_sem)
        else:
            print("No semesters found for the top year.")
            benchmark(year=test_year, semester=None)  # Fallback
    else:
        print("No data found.")
