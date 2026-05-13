#!/usr/bin/env python3
"""Deterministic architecture and API contract benchmark for autoresearch.

The workload intentionally avoids live network access and time-dependent inputs.
It combines executable API/data/categorizer contract checks with stdlib AST-based
maintainability metrics so future cleanup iterations are rewarded only when the
local API behavior still holds.
"""

from __future__ import annotations

import ast
import importlib
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data" / "classified" / "organized"
SOURCE_DIRS = (
    ROOT / "app_v2",
    ROOT / "config",
    ROOT / "scripts" / "processing",
    ROOT / "scraper",
)
SOURCE_FILE_EXCLUDES = frozenset({"__init__.py"})
API_KEY = "autoresearch-key"


@dataclass
class CheckSuite:
    """Collect contract checks without stopping at the first failure."""

    checks: int = 0
    failures: list[str] = field(default_factory=list)

    def require(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            self.failures.append(message)

    @property
    def failed(self) -> int:
        return len(self.failures)


@dataclass(frozen=True)
class StaticMetrics:
    modules: int
    source_lines: int
    public_functions: int
    max_function_lines: int
    long_functions: int
    max_cyclomatic_complexity: int
    complex_functions: int
    large_modules: int
    static_risk_score: int


class ComplexityVisitor(ast.NodeVisitor):
    """Small deterministic cyclomatic-complexity estimator."""

    def __init__(self) -> None:
        self.score = 1

    def visit_If(self, node: ast.If) -> Any:  # noqa: N802 - ast visitor API
        self.score += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> Any:  # noqa: N802
        self.score += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> Any:  # noqa: N802
        self.score += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> Any:  # noqa: N802
        self.score += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> Any:  # noqa: N802
        self.score += len(node.handlers) + (1 if node.orelse else 0) + (1 if node.finalbody else 0)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:  # noqa: N802
        self.score += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> Any:  # noqa: N802
        self.score += 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> Any:
        self.score += 1 + len(node.ifs)
        self.generic_visit(node)


class FunctionCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.functions: list[ast.AST] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa: N802
        self.functions.append(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:  # noqa: N802
        self.functions.append(node)
        self.generic_visit(node)


def iter_source_files() -> Iterable[Path]:
    for directory in SOURCE_DIRS:
        for path in sorted(directory.rglob("*.py")):
            if path.name in SOURCE_FILE_EXCLUDES:
                continue
            if "__pycache__" in path.parts:
                continue
            yield path


def _function_lines(node: ast.AST) -> int:
    end_line = getattr(node, "end_lineno", getattr(node, "lineno", 0))
    return max(1, end_line - getattr(node, "lineno", end_line) + 1)


def _function_complexity(node: ast.AST) -> int:
    visitor = ComplexityVisitor()
    visitor.visit(node)
    return visitor.score


def compute_static_metrics() -> StaticMetrics:
    modules = 0
    source_lines = 0
    public_functions = 0
    max_function_lines = 0
    long_functions = 0
    max_cyclomatic_complexity = 0
    complex_functions = 0
    large_modules = 0

    for path in iter_source_files():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        modules += 1
        source_lines += sum(1 for line in lines if line.strip() and not line.lstrip().startswith("#"))
        if len(lines) > 350:
            large_modules += 1

        tree = ast.parse(text, filename=str(path))
        collector = FunctionCollector()
        collector.visit(tree)
        for node in collector.functions:
            name = getattr(node, "name", "")
            if not name.startswith("_"):
                public_functions += 1
            function_lines = _function_lines(node)
            complexity = _function_complexity(node)
            max_function_lines = max(max_function_lines, function_lines)
            max_cyclomatic_complexity = max(max_cyclomatic_complexity, complexity)
            if function_lines > 50:
                long_functions += 1
            if complexity > 12:
                complex_functions += 1

    static_risk_score = (
        long_functions * 25
        + complex_functions * 40
        + large_modules * 30
        + max(0, max_function_lines - 75) * 2
        + max(0, max_cyclomatic_complexity - 15) * 10
    )
    return StaticMetrics(
        modules=modules,
        source_lines=source_lines,
        public_functions=public_functions,
        max_function_lines=max_function_lines,
        long_functions=long_functions,
        max_cyclomatic_complexity=max_cyclomatic_complexity,
        complex_functions=complex_functions,
        large_modules=large_modules,
        static_risk_score=static_risk_score,
    )


def configure_environment() -> None:
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ["LIBRARY_PORTAL_ENVIRONMENT"] = "production"
    os.environ["LIBRARY_PORTAL_API_KEY"] = API_KEY
    os.environ["LIBRARY_PORTAL_LOG_LEVEL"] = "ERROR"
    os.environ["LIBRARY_PORTAL_METRICS_ENABLED"] = "false"


def exercise_data_and_index(suite: CheckSuite) -> Any:
    from app_v2.data_loader import DataLoader
    from app_v2.services.indexing import PaperIndex

    loader = DataLoader(DATA_DIR)
    papers = loader.load_all()
    urls = [paper.get("url") for paper in papers if paper.get("url")]
    suite.require(len(papers) > 0, "data loader returned no papers")
    suite.require(len(urls) == len(set(urls)), "data loader returned duplicate URLs")
    suite.require(not loader.stats.errors, f"data loader errors: {loader.stats.errors}")
    suite.require(loader.stats.total_papers == len(papers), "loader total_papers mismatch")
    suite.require(loader.stats.unique_urls == len(set(urls)), "loader unique_urls mismatch")

    index = PaperIndex()
    index.load_from_directory(DataLoader(DATA_DIR))
    suite.require(index.total_papers == len(papers), "index total differs from loader")
    suite.require(len(index.unique_years) > 0, "index has no years")
    suite.require(len(index.unique_program_abbrevs) > 0, "index has no program abbreviations")
    suite.require(sum(index.count_by_year.values()) == index.total_papers, "year counts do not sum to total")
    suite.require(sum(index.count_by_program_abbrev.values()) == index.total_papers, "program abbreviation counts do not sum to total")
    return index


def _json(response: Any) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("expected JSON object")
    return payload


def exercise_api_contract(suite: CheckSuite, index: Any) -> None:
    config_module = importlib.import_module("config.config_v2")
    importlib.reload(config_module)
    main_module = importlib.import_module("app_v2.main")
    importlib.reload(main_module)

    headers = {"X-API-Key": API_KEY}
    with TestClient(main_module.app) as client:
        for path in ("/", "/health", "/openapi.json"):
            response = client.get(path)
            suite.require(response.status_code == 200, f"public endpoint {path} returned {response.status_code}")

        for path in ("/api/metadata", "/api/papers", "/health/data"):
            response = client.get(path)
            suite.require(response.status_code == 401, f"protected endpoint {path} without key returned {response.status_code}")
            suite.require("x-content-type-options" in response.headers, f"security headers missing on {path} 401")

        metadata_response = client.get("/api/metadata", headers=headers)
        suite.require(metadata_response.status_code == 200, "metadata endpoint failed with API key")
        metadata = _json(metadata_response)
        suite.require(set(metadata) >= {"years", "programs", "program_abbrevs", "semesters"}, "metadata response missing expected keys")
        suite.require(metadata.get("years") == list(index.unique_years), "metadata years differ from index")

        statistics_response = client.get("/api/statistics", headers=headers)
        suite.require(statistics_response.status_code == 200, "statistics endpoint failed")
        statistics = _json(statistics_response)
        suite.require(statistics.get("total_papers") == index.total_papers, "statistics total_papers differs from index")

        list_response = client.get("/api/papers", headers=headers, params={"limit": 5, "offset": 0})
        suite.require(list_response.status_code == 200, "papers list endpoint failed")
        list_payload = _json(list_response)
        suite.require(list_payload.get("total") == index.total_papers, "unfiltered papers total differs from index")
        suite.require(len(list_payload.get("papers", [])) == min(5, index.total_papers), "papers limit not honored")

        first_paper = sorted((paper for paper in index.papers if paper.get("url")), key=lambda item: item["url"])[0]
        lookup_response = client.get("/api/papers/lookup", headers=headers, params={"url": first_paper["url"]})
        suite.require(lookup_response.status_code == 200, "lookup endpoint failed for known URL")
        lookup_payload = _json(lookup_response)
        suite.require(lookup_payload.get("url") == first_paper["url"], "lookup returned wrong paper")

        if first_paper.get("course_code"):
            search_response = client.get("/api/papers", headers=headers, params={"search": first_paper["course_code"], "limit": 10})
            suite.require(search_response.status_code == 200, "search endpoint failed")
            search_payload = _json(search_response)
            suite.require(search_payload.get("total", 0) >= 1, "search for known course code returned no hits")

        first_abbrev = index.unique_program_abbrevs[0]
        abbrev_response = client.get("/api/papers", headers=headers, params={"program_abbrev": first_abbrev, "limit": 500})
        suite.require(abbrev_response.status_code == 200, "program_abbrev filter failed")
        abbrev_payload = _json(abbrev_response)
        suite.require(abbrev_payload.get("total") == index.count_by_program_abbrev[first_abbrev], "program_abbrev total differs from index")

        invalid_response = client.get("/api/papers", headers=headers, params={"semester": 99})
        suite.require(invalid_response.status_code == 422, "invalid semester did not fail validation")


def exercise_categorizer_contract(suite: CheckSuite) -> None:
    from scripts.processing.paper_categorizer import PaperCategorizer

    fixtures = (
        ({"course_code": "CSE2201", "program": "B.Tech", "year": 2024}, "btech/branches/CSE.json", "btech_branch"),
        ({"course_code": "CSS1001", "program": "B.Tech", "year": 2024}, "btech/first_year/cs_stream.json", "first_year_cs"),
        ({"course_code": "MAT1171", "program": "B.Tech", "year": 2024}, "btech/first_year/non_cs_stream.json", "first_year_core"),
        ({"course_code": "CSE5001", "program": "M.Tech", "year": 2024}, "masters/mtech.json", "masters"),
        ({"course_code": "ICS1001", "program": "B.Sc", "year": 2024}, "bsc/icas.json", "bsc"),
        ({"course_code": "ZZZ9001", "program": "Unknown", "year": 2024}, "other.json", "other"),
    )

    with tempfile.TemporaryDirectory(prefix="autoresearch-staging-") as staging_dir:
        categorizer = PaperCategorizer(DATA_DIR, Path(staging_dir))
        for paper, expected_suffix, expected_category in fixtures:
            result = categorizer.categorize(paper)
            target = result.target_file.relative_to(DATA_DIR).as_posix() if result.target_file else ""
            suite.require(target == expected_suffix, f"categorizer target for {paper['course_code']} was {target}")
            suite.require(result.category == expected_category, f"categorizer category for {paper['course_code']} was {result.category}")
            suite.require(result.confidence >= 0.5, f"categorizer confidence too low for {paper['course_code']}")


def main() -> int:
    configure_environment()
    suite = CheckSuite()

    static_metrics = compute_static_metrics()
    index = exercise_data_and_index(suite)
    exercise_api_contract(suite, index)
    exercise_categorizer_contract(suite)

    architecture_risk_score = static_metrics.static_risk_score + suite.failed * 100_000

    metrics = {
        "architecture_risk_score": architecture_risk_score,
        "contract_checks": suite.checks,
        "contract_failures": suite.failed,
        "static_risk_score": static_metrics.static_risk_score,
        "source_modules": static_metrics.modules,
        "source_lines": static_metrics.source_lines,
        "public_functions": static_metrics.public_functions,
        "long_functions": static_metrics.long_functions,
        "complex_functions": static_metrics.complex_functions,
        "large_modules": static_metrics.large_modules,
        "max_function_lines": static_metrics.max_function_lines,
        "max_cyclomatic_complexity": static_metrics.max_cyclomatic_complexity,
        "indexed_papers": index.total_papers,
    }

    for name, value in metrics.items():
        print(f"METRIC {name}={value}")

    if suite.failures:
        print("FAILURES:", file=sys.stderr)
        for failure in suite.failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
