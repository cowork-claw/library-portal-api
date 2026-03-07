import gc
import sys
import tracemalloc
from pathlib import Path

# Adjust path to import app_v2
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app_v2.data_loader import DataLoader
from app_v2.services.indexing import build_search_meta


def main():
    data_dir = Path("data/classified/organized")
    if not data_dir.exists():
        print(f"Data directory {data_dir} does not exist.")
        return

    loader = DataLoader(data_dir)
    papers = loader.load_all()

    tracemalloc.start()
    papers_copy = [dict(p) for p in papers]
    for paper in papers_copy:
        paper["_search_meta"] = build_search_meta(paper)
    current_unopt, peak_unopt = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del papers_copy
    gc.collect()

    tracemalloc.start()
    papers_copy_opt = [dict(p) for p in papers]

    field_meta_cache = {}
    for paper in papers_copy_opt:
        paper["_search_meta"] = build_search_meta(paper, field_meta_cache)

    current_opt, peak_opt = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Unoptimized Memory Usage: Current: {current_unopt / 10**6:.2f} MB")
    print(f"Unoptimized Memory Usage: Peak: {peak_unopt / 10**6:.2f} MB")
    print(f"Optimized Memory Usage: Current: {current_opt / 10**6:.2f} MB")
    print(f"Optimized Memory Usage: Peak: {peak_opt / 10**6:.2f} MB")
    if peak_unopt > 0:
        reduction_pct = (peak_unopt - peak_opt) / peak_unopt * 100
        print(f"Peak Reduction: {reduction_pct:.2f}%")
    else:
        print("Peak Reduction: N/A (baseline peak memory usage is zero)")


if __name__ == "__main__":
    main()
