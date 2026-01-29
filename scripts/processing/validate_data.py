"""
Data Validation for Library Portal V2

Validates the integrity of the organized data files.
Checks for:
- Valid JSON format
- Required paper fields
- URL uniqueness
- Correct file locations
"""

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
RECOMMENDED_FIELDS = {"year", "semester", "program", "degree_type", "paper_type"}


def validate_json_file(file_path: Path) -> Tuple[bool, List[str]]:
    """
    Validate a single JSON file.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except IOError as e:
        return False, [f"Cannot read file: {e}"]

    if not isinstance(data, dict):
        return False, ["Root must be a dictionary {course_code: [papers...]}"]

    paper_count = 0
    urls_seen = set()

    for course_code, papers in data.items():
        if not isinstance(papers, list):
            errors.append(f"Course {course_code}: value must be a list")
            continue

        for i, paper in enumerate(papers):
            paper_count += 1

            # Check required fields
            for field in REQUIRED_FIELDS:
                if field not in paper or paper[field] is None:
                    errors.append(
                        f"{course_code}[{i}]: missing required field '{field}'"
                    )

            # Check URL uniqueness
            url = paper.get("url")
            if url:
                if url in urls_seen:
                    errors.append(f"{course_code}[{i}]: duplicate URL")
                urls_seen.add(url)

            # Validate year if present
            year = paper.get("year")
            if year is not None:
                if not isinstance(year, int) or year < 2006 or year > 2030:
                    errors.append(f"{course_code}[{i}]: invalid year {year}")

            # Validate semester if present
            semester = paper.get("semester")
            if semester is not None:
                if not isinstance(semester, int) or semester < 1 or semester > 10:
                    errors.append(f"{course_code}[{i}]: invalid semester {semester}")

    if paper_count == 0:
        errors.append("File contains no papers")

    return len(errors) == 0, errors


def validate_all(data_dir: Path = DATA_DIRECTORY) -> Dict[str, Any]:
    """
    Validate all JSON files in the data directory.

    Returns:
        Validation report dictionary
    """
    report = {
        "valid": True,
        "files_checked": 0,
        "files_valid": 0,
        "files_invalid": 0,
        "total_papers": 0,
        "all_urls": set(),
        "duplicate_urls": [],
        "file_reports": {},
    }

    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        report["valid"] = False
        report["error"] = "Data directory not found"
        return report

    json_files = list(data_dir.rglob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files to validate")

    for json_file in json_files:
        relative_path = str(json_file.relative_to(data_dir))
        report["files_checked"] += 1

        is_valid, errors = validate_json_file(json_file)

        # Count papers
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for papers in data.values():
                if isinstance(papers, list):
                    report["total_papers"] += len(papers)
                    for paper in papers:
                        url = paper.get("url")
                        if url:
                            if url in report["all_urls"]:
                                report["duplicate_urls"].append(url)
                            report["all_urls"].add(url)
        except Exception:
            pass

        if is_valid:
            report["files_valid"] += 1
            logger.info(f"✅ {relative_path}")
        else:
            report["files_invalid"] += 1
            report["valid"] = False
            logger.error(f"❌ {relative_path}")
            for error in errors[:5]:  # Limit error output
                logger.error(f"   - {error}")
            if len(errors) > 5:
                logger.error(f"   ... and {len(errors) - 5} more errors")

        report["file_reports"][relative_path] = {"valid": is_valid, "errors": errors}

    # Summary
    logger.info("=" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info(f"  Files checked: {report['files_checked']}")
    logger.info(f"  Files valid: {report['files_valid']}")
    logger.info(f"  Files invalid: {report['files_invalid']}")
    logger.info(f"  Total papers: {report['total_papers']}")
    logger.info(f"  Unique URLs: {len(report['all_urls'])}")

    if report["duplicate_urls"]:
        logger.warning(f"  Duplicate URLs found: {len(report['duplicate_urls'])}")

    logger.info("=" * 60)

    # Convert set to list for JSON serialization
    report["all_urls"] = list(report["all_urls"])[:10]  # Sample only

    return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate organized data files")
    parser.add_argument(
        "--dir", type=Path, default=DATA_DIRECTORY, help="Data directory to validate"
    )
    parser.add_argument("--json", action="store_true", help="Output report as JSON")

    args = parser.parse_args()

    report = validate_all(args.dir)

    if args.json:
        import json

        print(json.dumps(report, indent=2, default=str))

    sys.exit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
