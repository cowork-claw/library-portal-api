import sys
import tracemalloc
from pathlib import Path

# Adjust path to import app_v2
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app_v2.data_loader import DataLoader


def main():
    data_dir = Path("data/classified/organized")
    if not data_dir.exists():
        print(f"Data directory {data_dir} does not exist.")
        return

    loader = DataLoader(data_dir)
    papers = loader.load_all()

    # Pre-optimization baseline approximation
    from app_v2.utils import WORD_TOKEN_PATTERN

    tracemalloc.start()
    papers_copy = [dict(p) for p in papers]

    for paper in papers_copy:
        paper["_search_meta"] = {
            field: {
                "lower": val_lower,
                "words": set(WORD_TOKEN_PATTERN.findall(val_lower)),
            }
            for field in [
                "course_code",
                "course_name",
                "subject_name",
                "display_title",
                "file_name",
            ]
            if (val := paper.get(field)) and (val_lower := str(val).lower())
        }
    current_unopt, peak_unopt = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tracemalloc.start()
    papers_copy_opt = [dict(p) for p in papers]

    field_meta_cache = {}
    for paper in papers_copy_opt:
        search_meta = {}
        for field in [
            "course_code",
            "course_name",
            "subject_name",
            "display_title",
            "file_name",
        ]:
            if (val := paper.get(field)) and (val_lower := str(val).lower()):
                if val_lower not in field_meta_cache:
                    field_meta_cache[val_lower] = {
                        "lower": val_lower,
                        "words": set(WORD_TOKEN_PATTERN.findall(val_lower)),
                    }
                search_meta[field] = field_meta_cache[val_lower]
        paper["_search_meta"] = search_meta

    current_opt, peak_opt = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Unoptimized Memory Usage: Current: {current_unopt / 10**6:.2f} MB")
    print(f"Optimized Memory Usage: Current: {current_opt / 10**6:.2f} MB")
    print(f"Reduction: {(current_unopt - current_opt) / current_unopt * 100:.2f}%")


if __name__ == "__main__":
    main()
