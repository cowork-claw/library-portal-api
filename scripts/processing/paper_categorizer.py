import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

AUTO_WRITE_CONFIDENCE = 0.85


@dataclass
class CategorizationResult:
    target_file: Path | None
    confidence: float
    category: str
    reasoning: list[str] = field(default_factory=list)
    metadata_filled: dict[str, Any] = field(default_factory=dict)


PREFIX_TO_BRANCH = {
    "AAE": "Aeronautical",
    "BME": "Biomedical",
    "BIO": "Biotechnology",
    "CHE": "Chemical",
    "CIV": "Civil",
    **dict.fromkeys(("CSE", "DSE", "ICT", "CSS"), "CSE"),
    "ECE": "ECE",
    **dict.fromkeys(("EEE", "ELE"), "EEE"),
    "ICE": "EIE",
    "IND": "Industrial",
    "INF": "IT",
    **dict.fromkeys(("MEC", "MME"), "Mechanical"),
    "MTE": "Mechatronics",
    "MED": "MediaPrint",
}

FIRST_YEAR_PREFIX_PATTERN = re.compile(
    r"^(MAT|PHY|CHM|HUM|CIE|MME|IPE|BIO|EEE|ELE|CIV|CSS|ECE)$"
)
CS_STREAM_PATTERN = re.compile(r"^[A-Z]{2,3}1[0-2]02$")
CSS_PREFIX_PATTERN = re.compile(r"^CSS\d{4}$")
CORE_STREAM_PATTERN = re.compile(r"^[A-Z]{2,3}1[0-2]7[12]$")
FIRST_YEAR_CSS_RESULT = (
    "cs_stream.json",
    0.95,
    "first_year_cs",
    "cs",
    "CSS prefix = CS Stream (2024+)",
)
FIRST_YEAR_CS_RESULT = ("cs_stream.json", 0.9, "first_year_cs", "cs")
FIRST_YEAR_CORE_RESULT = ("non_cs_stream.json", 0.9, "first_year_core", "core")
ICAS_PREFIXES = {"ICS", "IMA", "IPH", "ICH", "IBI"}
MASTERS_PATTERN = re.compile(
    r"\b(m\s*\.?\s*tech|mtech|m\s*\.?\s*e\.?|mca|m\s*\.?\s*sc|msc)\b",
    re.IGNORECASE,
)
MASTERS_CATEGORIES = {
    "MCA": ("mca.json", 0.9, "MCA program detected"),
    "M.E": ("me.json", 0.9, "M.E program detected"),
    "M.Tech": ("mtech.json", 0.85, "M.Tech program detected (default masters)"),
}

logger = logging.getLogger(__name__)


def _write_paper_to_file(paper: dict[str, Any], target_file: Path) -> bool:
    try:
        if target_file.exists():
            with open(target_file, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        if not isinstance(data, dict):
            data = {}

        course_code = paper.get("course_code", "UNKNOWN")
        papers = data.get(course_code)
        if not isinstance(papers, list):
            papers = data[course_code] = []

        existing_urls = {p.get("url") for p in papers if isinstance(p, dict)}
        if paper.get("url") in existing_urls:
            logger.debug(f"Paper already exists in {target_file}: {paper.get('url')}")
            return False

        papers.append(paper)
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)

        logger.info(f"Added paper to {target_file}: {course_code}")
        return True

    except Exception as e:
        logger.error(f"Error writing paper to {target_file}: {e}")
        return False


class PaperCategorizer:
    def __init__(self, data_directory: Path) -> None:
        self.data_dir = data_directory

    def _normalized_course_code(self, paper: dict[str, Any]) -> str:
        course_code = str(
            paper.get("course_code", "") or paper.get("subject_code", "")
        ).upper()
        return re.sub(r"\s+", "", course_code.strip())

    def _course_prefix(self, course_code: str) -> str:
        prefix_match = re.match(r"^([A-Z]{2,4})", course_code)
        return prefix_match.group(1) if prefix_match else ""

    def _categorize_icas(
        self, prefix: str, reasoning: list[str]
    ) -> CategorizationResult:
        reasoning.append(f"ICAS pattern detected: {prefix}")
        return CategorizationResult(
            self.data_dir / "bsc" / "icas.json",
            0.85,
            "bsc",
            reasoning,
            {"degree_type": "B.Sc"},
        )

    def _categorize_btech_branch(
        self, prefix: str, course_code: str, reasoning: list[str]
    ) -> CategorizationResult | None:
        branch = PREFIX_TO_BRANCH.get(prefix)
        if not branch:
            return None

        target = self.data_dir / "btech" / "branches" / f"{branch}.json"
        if not target.exists():
            reasoning.append(f"Branch file not found: {branch}.json")
            return None

        metadata: dict[str, Any] = {"degree_type": "B.Tech"}
        confidence = 0.85
        reasoning.append(f"Branch mapped: {prefix} → {branch}")

        if semester := self._get_semester_from_code(course_code):
            metadata["semester"] = semester
            reasoning.append(f"Semester extracted: {semester}")
            confidence += 0.05

        return CategorizationResult(
            target, confidence, "btech_branch", reasoning, metadata
        )

    def _categorize(self, paper: dict[str, Any]) -> CategorizationResult:
        reasoning: list[str] = []
        course_code = self._normalized_course_code(paper)
        program = str(paper.get("program", "") or "")
        degree_type = str(paper.get("degree_type", "") or "")
        prefix = self._course_prefix(course_code)

        if not prefix:
            reasoning.append("Could not extract prefix from course code")
            return CategorizationResult(None, 0.1, "uncertain", reasoning, {})

        reasoning.append(f"Valid prefix: {prefix}")
        if degree := self._masters_degree(program, degree_type, course_code):
            return self._categorize_masters(degree, reasoning)

        if self._is_icas(prefix):
            return self._categorize_icas(prefix, reasoning)

        if first_year_result := self._check_first_year(
            course_code, prefix, reasoning.copy()
        ):
            return first_year_result

        branch_result = self._categorize_btech_branch(prefix, course_code, reasoning)
        if branch_result is not None:
            return branch_result

        reasoning.append("No clear category - defaulting to other.json")
        return CategorizationResult(
            self.data_dir / "other.json", 0.5, "other", reasoning, {}
        )

    def _masters_degree(
        self, program: str, degree_type: str, course_code: str
    ) -> str | None:
        descriptor = f"{program} {degree_type}"
        if not MASTERS_PATTERN.search(descriptor) and not re.match(
            r"^[A-Z]{2,4}5\d{3}$", course_code
        ):
            return None
        if re.search(r"\bmca\b", descriptor, re.IGNORECASE):
            return "MCA"
        if re.search(r"\bm\s*\.?\s*e\.?\b", descriptor, re.IGNORECASE):
            return "M.E"
        return "M.Tech"

    def _categorize_masters(
        self, degree: str, reasoning: list[str]
    ) -> CategorizationResult:
        filename, confidence, reason = MASTERS_CATEGORIES[degree]
        reasoning.append(reason)
        return CategorizationResult(
            self.data_dir / "masters" / filename,
            confidence,
            "masters",
            reasoning,
            {"degree_type": degree},
        )

    def _is_icas(self, prefix: str) -> bool:
        return prefix in ICAS_PREFIXES or (
            prefix.startswith("I") and prefix not in {"ICE", "ICT", "IND", "INF"}
        )

    def _check_first_year(
        self, course_code: str, prefix: str, reasoning: list[str]
    ) -> CategorizationResult | None:
        if CSS_PREFIX_PATTERN.match(course_code) or prefix == "CSS":
            result_args = FIRST_YEAR_CSS_RESULT
        elif CS_STREAM_PATTERN.match(course_code):
            result_args = (
                *FIRST_YEAR_CS_RESULT,
                f"CS Stream pattern matched: {course_code}",
            )
        elif CORE_STREAM_PATTERN.match(course_code):
            result_args = (
                *FIRST_YEAR_CORE_RESULT,
                f"Core Stream pattern matched: {course_code}",
            )
        else:
            if FIRST_YEAR_PREFIX_PATTERN.match(prefix):
                reasoning.append(f"First year prefix ({prefix}) but unclear pattern")
            return None

        filename, confidence, category, stream, reason = result_args
        reasoning.append(reason)
        return CategorizationResult(
            self.data_dir / "btech" / "first_year" / filename,
            confidence,
            category,
            reasoning,
            {"degree_type": "B.Tech", "streams": [stream]},
        )

    def _get_semester_from_code(self, code: str) -> int | None:
        match = re.match(r"^[A-Z]{2,4}(\d)(\d)", code)
        if not match:
            return None

        year_digit, sem_type = int(match.group(1)), int(match.group(2))
        if year_digit == 1:
            return {0: 1, 1: 1, 2: 2, 7: 1}.get(sem_type)
        if year_digit in (2, 3) and sem_type in (1, 2):
            return (year_digit - 1) * 2 + sem_type
        if year_digit == 4:
            return 7 if sem_type < 2 else 8
        return None
