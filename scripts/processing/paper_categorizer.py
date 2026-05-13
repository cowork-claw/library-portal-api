"""Categorize scraped papers into organized JSON targets."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paper_categorizer_rules import (
    CORE_STREAM_PATTERN,
    CS_STREAM_PATTERN,
    CSS_PREFIX_PATTERN,
    FIRST_YEAR_CORE_PREFIXES,
    FIRST_YEAR_CS_PREFIXES,
    ICAS_PREFIXES,
    PREFIX_TO_BRANCH,
    SEMESTER_BY_CODE_DIGITS,
    CategorizationResult,
)

logger = logging.getLogger(__name__)


def write_paper_to_file(paper: Dict[str, Any], target_file: Path) -> bool:
    """Write a categorized paper into an organized JSON file."""
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


class PaperCategorizer:
    """Categorize papers by target file, confidence, and derived metadata."""

    def __init__(self, data_directory: Path, staging_directory: Path) -> None:
        """Initialize with organized data and staging directories."""
        self.data_dir = data_directory
        self.staging_dir = staging_directory
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def _normalized_course_code(self, paper: Dict[str, Any]) -> str:
        """Return a compact uppercase course code from scraper fields."""
        course_code = str(
            paper.get("course_code", "") or paper.get("subject_code", "")
        ).upper()
        return re.sub(r"\s+", "", course_code.strip())

    def _course_prefix(self, course_code: str) -> str:
        """Extract the alphabetic course prefix, if present."""
        prefix_match = re.match(r"^([A-Z]{2,4})", course_code)
        return prefix_match.group(1) if prefix_match else ""

    def _uncertain_result(self, reasoning: List[str]) -> CategorizationResult:
        """Return the standard low-confidence result for malformed course codes."""
        reasoning.append("Could not extract prefix from course code")
        return CategorizationResult(None, 0.1, "uncertain", reasoning, {})

    def _categorize_icas(
        self, prefix: str, reasoning: List[str]
    ) -> CategorizationResult:
        """Return the B.Sc ICAS categorization result."""
        reasoning.append(f"ICAS pattern detected: {prefix}")
        return CategorizationResult(
            self.data_dir / "bsc" / "icas.json",
            0.85,
            "bsc",
            reasoning,
            {"degree_type": "B.Sc"},
        )

    def _categorize_btech_branch(
        self, prefix: str, course_code: str, reasoning: List[str]
    ) -> Optional[CategorizationResult]:
        """Return a B.Tech branch result when the prefix maps to an existing file."""
        branch = PREFIX_TO_BRANCH.get(prefix)
        if not branch:
            return None

        target = self.data_dir / "btech" / "branches" / f"{branch}.json"
        if not target.exists():
            reasoning.append(f"Branch file not found: {branch}.json")
            return None

        metadata: Dict[str, Any] = {"degree_type": "B.Tech"}
        confidence = 0.85
        reasoning.append(f"Branch mapped: {prefix} → {branch}")

        semester = self._get_semester_from_code(course_code)
        if semester:
            metadata["semester"] = semester
            reasoning.append(f"Semester extracted: {semester}")
            confidence += 0.05

        return CategorizationResult(
            target, confidence, "btech_branch", reasoning, metadata
        )

    def _categorize_other(
        self, reasoning: List[str], metadata: Dict[str, Any]
    ) -> CategorizationResult:
        """Return the fallback catch-all categorization result."""
        reasoning.append("No clear category - defaulting to other.json")
        return CategorizationResult(
            self.data_dir / "other.json", 0.5, "other", reasoning, metadata
        )

    def categorize(self, paper: Dict[str, Any]) -> CategorizationResult:
        """Determine the target file, confidence, and reasoning for a paper."""
        reasoning: List[str] = []
        metadata: Dict[str, Any] = {}
        course_code = self._normalized_course_code(paper)
        program = str(paper.get("program", "") or "")
        degree_type = str(paper.get("degree_type", "") or "")
        prefix = self._course_prefix(course_code)

        if not prefix:
            return self._uncertain_result(reasoning)

        reasoning.append(f"Valid prefix: {prefix}")
        if self._is_masters(program, degree_type, course_code):
            return self._categorize_masters(
                program, degree_type, prefix, course_code, reasoning
            )

        if self._is_icas(prefix, course_code):
            return self._categorize_icas(prefix, reasoning)

        first_year_result = self._check_first_year(
            course_code, prefix, reasoning.copy()
        )
        if first_year_result is not None:
            return first_year_result

        branch_result = self._categorize_btech_branch(prefix, course_code, reasoning)
        if branch_result is not None:
            return branch_result

        return self._categorize_other(reasoning, metadata)

    def _is_masters(self, program: str, degree_type: str, course_code: str) -> bool:
        """Return whether scraper metadata or course code indicates masters level."""
        masters_keywords = ["M.Tech", "MTech", "M.E", "ME", "MCA", "M.Sc", "MSc"]

        for keyword in masters_keywords:
            if (
                keyword.lower() in program.lower()
                or keyword.lower() in degree_type.lower()
            ):
                return True

        # Course codes starting with 5XXX are typically masters level
        if re.match(r"^[A-Z]{2,4}5\d{3}$", course_code):
            return True

        return False

    def _categorize_masters(
        self,
        program: str,
        degree_type: str,
        prefix: str,
        course_code: str,
        reasoning: List[str],
    ) -> CategorizationResult:
        """Categorize a masters-level paper by program family."""
        if "MCA" in program or "MCA" in degree_type:
            reasoning.append("MCA program detected")
            return CategorizationResult(
                self.data_dir / "masters" / "mca.json",
                0.9,
                "masters",
                reasoning,
                {"degree_type": "MCA"},
            )

        if "M.E" in program or "ME" == degree_type:
            reasoning.append("M.E program detected")
            return CategorizationResult(
                self.data_dir / "masters" / "me.json",
                0.9,
                "masters",
                reasoning,
                {"degree_type": "M.E"},
            )

        # Default to M.Tech
        reasoning.append("M.Tech program detected (default masters)")
        return CategorizationResult(
            self.data_dir / "masters" / "mtech.json",
            0.85,
            "masters",
            reasoning,
            {"degree_type": "M.Tech"},
        )

    def _is_icas(self, prefix: str, course_code: str) -> bool:
        """Return whether the prefix/course code belongs to B.Sc ICAS."""
        # ICAS codes start with 'I' followed by subject area
        if prefix in ICAS_PREFIXES:
            return True

        # General I-prefix that's not a known engineering prefix
        engineering_i_prefixes = {"ICE", "ICT", "IND", "INF"}
        if prefix.startswith("I") and prefix not in engineering_i_prefixes:
            return True

        return False

    def _first_year_result(
        self,
        filename: str,
        confidence: float,
        category: str,
        stream: str,
        reason: str,
        reasoning: List[str],
    ) -> CategorizationResult:
        """Build a first-year categorization result with stream metadata."""
        reasoning.append(reason)
        return CategorizationResult(
            self.data_dir / "btech" / "first_year" / filename,
            confidence,
            category,
            reasoning,
            {"degree_type": "B.Tech", "streams": [stream]},
        )

    def _check_first_year(
        self, course_code: str, prefix: str, reasoning: List[str]
    ) -> Optional[CategorizationResult]:
        """Return a first-year stream result when the course pattern is known."""
        if CSS_PREFIX_PATTERN.match(course_code) or prefix == "CSS":
            return self._first_year_result(
                "cs_stream.json",
                0.95,
                "first_year_cs",
                "cs",
                "CSS prefix = CS Stream (2024+)",
                reasoning,
            )

        if CS_STREAM_PATTERN.match(course_code):
            return self._first_year_result(
                "cs_stream.json",
                0.9,
                "first_year_cs",
                "cs",
                f"CS Stream pattern matched: {course_code}",
                reasoning,
            )

        if CORE_STREAM_PATTERN.match(course_code):
            return self._first_year_result(
                "non_cs_stream.json",
                0.9,
                "first_year_core",
                "core",
                f"Core Stream pattern matched: {course_code}",
                reasoning,
            )

        if prefix in FIRST_YEAR_CORE_PREFIXES or prefix in FIRST_YEAR_CS_PREFIXES:
            reasoning.append(f"First year prefix ({prefix}) but unclear pattern")

        return None

    def _get_semester_from_code(self, code: str) -> Optional[int]:
        """Extract semester number 1-8 from a branch course code."""
        match = re.match(r"^[A-Z]{2,4}(\d)(\d)", code)
        if not match:
            return None

        return SEMESTER_BY_CODE_DIGITS.get((int(match.group(1)), int(match.group(2))))
