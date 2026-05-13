"""
Paper Categorizer for Library Portal V2

Intelligent categorization of scraped papers into the organized folder structure.
Uses course code patterns and program information to determine target file.

Key features:
- 2024+ two-track first year detection (CS vs Core)
- Confidence scoring for auto-write vs staging
- CSS prefix handling for new curriculum
"""

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
from .paper_writer import write_paper_to_file as write_paper_to_file


class PaperCategorizer:
    """
    Categorizes papers into the organized folder structure.

    Uses course code patterns and program information to determine:
    1. Target JSON file
    2. Confidence score
    3. Any metadata that can be auto-filled
    """

    def __init__(self, data_directory: Path, staging_directory: Path) -> None:
        """
        Initialize the PaperCategorizer.

        Args:
            data_directory: Path to the organized data folder.
            staging_directory: Path to the folder for papers needing review.
        """
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
        """
        Determine the correct file for a paper and calculate confidence.

        Args:
            paper: Paper dictionary from scraper

        Returns:
            CategorizationResult with target file, confidence, and reasoning
        """
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
        """
        Check if a paper belongs to a Master's program.

        Args:
            program: The program name from the paper.
            degree_type: The degree type from the paper.
            course_code: The course code of the paper.

        Returns:
            True if the paper is determined to be a Master's level paper.
        """
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
        """
        Categorize a paper determined to be for a Master's program.

        Args:
            program: The program name from the paper.
            degree_type: The degree type from the paper.
            prefix: The extracted course code prefix.
            course_code: The full course code.
            reasoning: A list of reasons for the categorization.

        Returns:
            A CategorizationResult for the Master's paper.
        """
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
        """
        Check if a paper belongs to the B.Sc ICAS program.

        Args:
            prefix: The extracted course code prefix.
            course_code: The full course code.

        Returns:
            True if the paper is determined to be an ICAS paper.
        """
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
        """
        Check if a paper is a first-year paper and determine its stream.

        Args:
            course_code: The full course code.
            prefix: The extracted course code prefix.
            reasoning: A list of reasons for the categorization.

        Returns:
            A CategorizationResult if the paper is a first-year paper, otherwise None.
        """
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
        """
        Extract semester from the course code pattern.

        Args:
            code: The course code.

        Returns:
            The extracted semester number (1-8) or None if not found.
        """
        match = re.match(r"^[A-Z]{2,4}(\d)(\d)", code)
        if not match:
            return None

        return SEMESTER_BY_CODE_DIGITS.get((int(match.group(1)), int(match.group(2))))
