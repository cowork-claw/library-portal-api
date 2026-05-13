"""Validate organized paper JSON files."""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scraper.scraper_config import DATA_DIRECTORY

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# Required fields for each paper
REQUIRED_FIELDS = {"url", "file_name", "course_code"}


def _load_json(file_path: Path) -> Tuple[Any, List[str]]:
    """Load JSON data from disk and return validation-style read errors."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f), []
    except json.JSONDecodeError as e:
        return None, [f"Invalid JSON: {e}"]
    except IOError as e:
        return None, [f"Cannot read file: {e}"]


def _validate_required_fields(
    course_code: str, index: int, paper: Dict[str, Any], errors: List[str]
) -> None:
    """Record missing required paper fields."""
    for field in REQUIRED_FIELDS:
        if field not in paper or paper[field] is None:
            errors.append(f"{course_code}[{index}]: missing required field '{field}'")


def _validate_unique_url(
    course_code: str,
    index: int,
    paper: Dict[str, Any],
    urls_seen: set,
    errors: List[str],
) -> None:
    """Record duplicate URLs within a single JSON file."""
    url = paper.get("url")
    if not url:
        return
    if url in urls_seen:
        errors.append(f"{course_code}[{index}]: duplicate URL")
    urls_seen.add(url)


def _validate_int_range(
    course_code: str,
    index: int,
    paper: Dict[str, Any],
    field: str,
    lower: int,
    upper: int,
    errors: List[str],
) -> None:
    """Record invalid optional integer range fields."""
    value = paper.get(field)
    if value is None:
        return
    if not isinstance(value, int) or value < lower or value > upper:
        errors.append(f"{course_code}[{index}]: invalid {field} {value}")


def _validate_paper(
    course_code: str,
    index: int,
    paper: Dict[str, Any],
    urls_seen: set,
    errors: List[str],
) -> None:
    """Validate one paper record."""
    _validate_required_fields(course_code, index, paper, errors)
    _validate_unique_url(course_code, index, paper, urls_seen, errors)
    _validate_int_range(course_code, index, paper, "year", 2006, 2030, errors)
    _validate_int_range(course_code, index, paper, "semester", 1, 10, errors)


def _validate_json_file(file_path: Path) -> Tuple[bool, List[str]]:
    """Validate one course-code JSON file."""
    data, errors = _load_json(file_path)
    if errors:
        return False, errors
    if not isinstance(data, dict):
        return False, ["Root must be a dictionary {course_code: [papers...]}"]

    paper_count = 0
    urls_seen = set()
    for course_code, papers in data.items():
        if not isinstance(papers, list):
            errors.append(f"Course {course_code}: value must be a list")
            continue
        for index, paper in enumerate(papers):
            paper_count += 1
            _validate_paper(course_code, index, paper, urls_seen, errors)

    if paper_count == 0:
        errors.append("File contains no papers")
    return len(errors) == 0, errors


def _new_report() -> Dict[str, Any]:
    """Create an empty validation report."""
    return {
        "valid": True,
        "files_checked": 0,
        "files_valid": 0,
        "files_invalid": 0,
        "total_papers": 0,
        "all_urls": set(),
        "duplicate_urls": [],
        "file_reports": {},
    }


def _count_file_papers(report: Dict[str, Any], json_file: Path) -> None:
    """Update cross-file paper and URL counts from one JSON file."""
    data, errors = _load_json(json_file)
    if errors or not isinstance(data, dict):
        return

    for papers in data.values():
        if not isinstance(papers, list):
            continue
        report["total_papers"] += len(papers)
        for paper in papers:
            url = paper.get("url")
            if not url:
                continue
            if url in report["all_urls"]:
                report["duplicate_urls"].append(url)
            report["all_urls"].add(url)


def _record_file_result(
    report: Dict[str, Any], relative_path: str, is_valid: bool, errors: List[str]
) -> None:
    """Update aggregate report counters for one file result."""
    if is_valid:
        report["files_valid"] += 1
        logger.info("OK %s", relative_path)
    else:
        report["files_invalid"] += 1
        report["valid"] = False
        logger.error("FAIL %s", relative_path)
        for error in errors[:5]:
            logger.error("   - %s", error)
        if len(errors) > 5:
            logger.error("   ... and %d more errors", len(errors) - 5)

    report["file_reports"][relative_path] = {"valid": is_valid, "errors": errors}


def _log_summary(report: Dict[str, Any]) -> None:
    """Log aggregate validation results."""
    logger.info("=" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info("  Files checked: %s", report["files_checked"])
    logger.info("  Files valid: %s", report["files_valid"])
    logger.info("  Files invalid: %s", report["files_invalid"])
    logger.info("  Total papers: %s", report["total_papers"])
    logger.info("  Unique URLs: %s", len(report["all_urls"]))

    if report["duplicate_urls"]:
        logger.warning("  Duplicate URLs found: %s", len(report["duplicate_urls"]))

    logger.info("=" * 60)


def _validate_all(data_dir: Path = DATA_DIRECTORY) -> Dict[str, Any]:
    """Validate all JSON files under the data directory."""
    report = _new_report()
    if not data_dir.exists():
        logger.error("Data directory not found: %s", data_dir)
        report["valid"] = False
        report["error"] = "Data directory not found"
        return report

    json_files = list(data_dir.rglob("*.json"))
    logger.info("Found %d JSON files to validate", len(json_files))

    for json_file in json_files:
        relative_path = str(json_file.relative_to(data_dir))
        report["files_checked"] += 1
        is_valid, errors = _validate_json_file(json_file)
        _count_file_papers(report, json_file)
        _record_file_result(report, relative_path, is_valid, errors)

    _log_summary(report)
    report["all_urls"] = list(report["all_urls"])[:10]
    return report


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Validate organized data files")
    parser.add_argument(
        "--dir", type=Path, default=DATA_DIRECTORY, help="Data directory to validate"
    )
    parser.add_argument("--json", action="store_true", help="Output report as JSON")

    args = parser.parse_args()

    report = _validate_all(args.dir)

    if args.json:
        import json

        print(json.dumps(report, indent=2, default=str))

    sys.exit(0 if report["valid"] else 1)


if __name__ == "__main__":
    _main()
