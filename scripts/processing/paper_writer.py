"""Write categorized papers into organized JSON files."""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def write_paper_to_file(paper: Dict[str, Any], target_file: Path) -> bool:
    """
    Write a paper to the target JSON file.

    The file format is: {course_code: [papers...]}

    Args:
        paper: The paper dictionary to write.
        target_file: The path to the JSON file where the paper should be stored.

    Returns:
        True if the paper was successfully written (or was a duplicate), False otherwise.
    """
    try:
        if target_file.exists():
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}

        course_code = paper.get("course_code", "UNKNOWN")
        if course_code not in data:
            data[course_code] = []

        existing_urls = {p.get("url") for p in data[course_code]}
        if paper.get("url") in existing_urls:
            logger.debug(f"Paper already exists in {target_file}: {paper.get('url')}")
            return False

        data[course_code].append(paper)
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)

        logger.info(f"Added paper to {target_file}: {course_code}")
        return True

    except Exception as e:
        logger.error(f"Error writing paper to {target_file}: {e}")
        return False
