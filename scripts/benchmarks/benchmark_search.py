import time

from app_v2.data_loader import DataLoader
from app_v2.services.indexing import PaperIndex
from app_v2.services.search import search_papers


# Mock DataLoader to feed PaperIndex
class MockLoader(DataLoader):
    def __init__(self):
        self.papers = []
        # Create 3000 dummy papers to simulate load
        for i in range(3000):
            self.papers.append(
                {
                    "url": f"http://example.com/{i}",
                    "course_code": f"CSE{2000+i}",
                    "course_name": f"Computer Science {i} Algorithms and Data Structures",
                    "subject_name": "Data Structures",
                    "display_title": f"End Semester Examination {2000+i}",
                    "file_name": f"paper_{i}.pdf",
                    "year": 2020 + (i % 5),
                }
            )

    def load_all(self):
        return self.papers

    def get_stats(self):
        return {"files_loaded": 1}


def benchmark():
    # Setup
    loader = MockLoader()
    index = PaperIndex()
    index.load_from_directory(loader)

    papers = index.papers
    query = "Algorithms"

    print(f"Benchmarking search on {len(papers)} papers...")

    # Warmup
    search_papers(papers[:100], query)

    # Benchmark
    start_time = time.time()
    iterations = 50
    for _ in range(iterations):
        search_papers(papers, query)
    end_time = time.time()

    avg_time = (end_time - start_time) / iterations
    print(f"Average search time over {iterations} iterations: {avg_time:.4f} seconds")


if __name__ == "__main__":
    benchmark()
