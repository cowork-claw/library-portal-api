import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config_v2 import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
DATA_DIRECTORY = settings.DATA_DIRECTORY


# Required fields for each paper
REQUIRED_FIELDS = {"url", "file_name", "course_code"}


def _load_json(file_path: Path) -> tuple[Any, list[str]]:
    try:
        return json.loads(file_path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as e:
        return None, [f"Invalid JSON: {e}"]
    except OSError as e:
        return None, [f"Cannot read file: {e}"]


def _validate_required_fields(
    course_code: str, index: int, paper: dict[str, Any], errors: list[str]
) -> None:
    for field in REQUIRED_FIELDS:
        if field not in paper or paper[field] is None:
            errors.append(f"{course_code}[{index}]: missing required field '{field}'")


def _validate_unique_url(
    course_code: str,
    index: int,
    paper: dict[str, Any],
    urls_seen: set,
    errors: list[str],
) -> None:
    if url := paper.get("url"):
        if url in urls_seen:
            errors.append(f"{course_code}[{index}]: duplicate URL")
        urls_seen.add(url)


def _validate_int_range(
    course_code: str,
    index: int,
    paper: dict[str, Any],
    field: str,
    lower: int,
    upper: int,
    errors: list[str],
) -> None:
    value = paper.get(field)
    if value is not None and not (isinstance(value, int) and lower <= value <= upper):
        errors.append(f"{course_code}[{index}]: invalid {field} {value}")


def _validate_json_file(file_path: Path) -> tuple[bool, list[str]]:
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
            _validate_required_fields(course_code, index, paper, errors)
            _validate_unique_url(course_code, index, paper, urls_seen, errors)
            _validate_int_range(course_code, index, paper, "year", 2006, 2030, errors)
            _validate_int_range(course_code, index, paper, "semester", 1, 10, errors)

    if paper_count == 0:
        errors.append("File contains no papers")
    return len(errors) == 0, errors


def _new_report() -> dict[str, Any]:
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


def _count_file_papers(report: dict[str, Any], json_file: Path) -> None:
    data, errors = _load_json(json_file)
    if errors or not isinstance(data, dict):
        return

    for papers in data.values():
        if not isinstance(papers, list):
            continue
        report["total_papers"] += len(papers)
        for paper in papers:
            if url := paper.get("url"):
                if url in report["all_urls"]:
                    report["duplicate_urls"].append(url)
                report["all_urls"].add(url)


def _record_file_result(
    report: dict[str, Any], relative_path: str, is_valid: bool, errors: list[str]
) -> None:
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


def _log_summary(report: dict[str, Any]) -> None:
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


def _validate_all(data_dir: Path = DATA_DIRECTORY) -> dict[str, Any]:
    report = _new_report()
    if not data_dir.exists():
        logger.error("Data directory not found: %s", data_dir)
        report["valid"] = False
        report["error"] = "Data directory not found"
        return report

    for json_file in data_dir.rglob("*.json"):
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
        print(json.dumps(report, indent=2, default=str))

    sys.exit(0 if report["valid"] else 1)


if __name__ == "__main__":
    _main()
