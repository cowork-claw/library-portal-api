import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

AUTO_WRITE_CONFIDENCE = 0.85


@dataclass
class CategorizationResult:
    target_file: Optional[Path]
    confidence: float
    category: str
    reasoning: List[str] = field(default_factory=list)
    metadata_filled: Dict[str, Any] = field(default_factory=dict)


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
CS_STREAM_PATTERN = re.compile(r"^[A-Z]{2,3}1[0-2]0[0-9]$")
CSS_PREFIX_PATTERN = re.compile(r"^CSS\d{4}$")
CORE_STREAM_PATTERN = re.compile(r"^[A-Z]{2,3}1[0-2]7[12]$")
ICAS_PREFIXES = {"ICS", "IMA", "IPH", "ICH", "IBI"}
MASTERS_CATEGORIES = {
    "MCA": ("mca.json", 0.9, "MCA program detected"),
    "M.E": ("me.json", 0.9, "M.E program detected"),
    "M.Tech": ("mtech.json", 0.85, "M.Tech program detected (default masters)"),
}

logger = logging.getLogger(__name__)


def _write_paper_to_file(paper: Dict[str, Any], target_file: Path) -> bool:
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
    def __init__(self, data_directory: Path, staging_directory: Path) -> None:
        self.data_dir = data_directory
        self.staging_dir = staging_directory
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def _normalized_course_code(self, paper: Dict[str, Any]) -> str:
        course_code = str(
            paper.get("course_code", "") or paper.get("subject_code", "")
        ).upper()
        return re.sub(r"\s+", "", course_code.strip())

    def _course_prefix(self, course_code: str) -> str:
        prefix_match = re.match(r"^([A-Z]{2,4})", course_code)
        return prefix_match.group(1) if prefix_match else ""

    def _uncertain_result(self, reasoning: List[str]) -> CategorizationResult:
        reasoning.append("Could not extract prefix from course code")
        return CategorizationResult(None, 0.1, "uncertain", reasoning, {})

    def _categorize_icas(
        self, prefix: str, reasoning: List[str]
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
        self, prefix: str, course_code: str, reasoning: List[str]
    ) -> Optional[CategorizationResult]:
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

        if semester := self._get_semester_from_code(course_code):
            metadata["semester"] = semester
            reasoning.append(f"Semester extracted: {semester}")
            confidence += 0.05

        return CategorizationResult(
            target, confidence, "btech_branch", reasoning, metadata
        )

    def _categorize_other(self, reasoning: List[str]) -> CategorizationResult:
        reasoning.append("No clear category - defaulting to other.json")
        return CategorizationResult(
            self.data_dir / "other.json", 0.5, "other", reasoning, {}
        )

    def _categorize(self, paper: Dict[str, Any]) -> CategorizationResult:
        reasoning: List[str] = []
        course_code = self._normalized_course_code(paper)
        program = str(paper.get("program", "") or "")
        degree_type = str(paper.get("degree_type", "") or "")
        prefix = self._course_prefix(course_code)

        if not prefix:
            return self._uncertain_result(reasoning)

        reasoning.append(f"Valid prefix: {prefix}")
        if self._is_masters(program, degree_type, course_code):
            return self._categorize_masters(program, degree_type, reasoning)

        if self._is_icas(prefix, course_code):
            return self._categorize_icas(prefix, reasoning)

        if first_year_result := self._check_first_year(
            course_code, prefix, reasoning.copy()
        ):
            return first_year_result

        branch_result = self._categorize_btech_branch(prefix, course_code, reasoning)
        if branch_result is not None:
            return branch_result

        return self._categorize_other(reasoning)

    def _is_masters(self, program: str, degree_type: str, course_code: str) -> bool:
        program_lower, degree_type_lower = program.lower(), degree_type.lower()
        return any(
            keyword in program_lower or keyword in degree_type_lower
            for keyword in ("m.tech", "mtech", "m.e", "me", "mca", "m.sc", "msc")
        ) or bool(re.match(r"^[A-Z]{2,4}5\d{3}$", course_code))

    def _categorize_masters(
        self, program: str, degree_type: str, reasoning: List[str]
    ) -> CategorizationResult:
        degree = (
            "MCA"
            if "MCA" in program or "MCA" in degree_type
            else "M.E" if "M.E" in program or "ME" == degree_type else "M.Tech"
        )
        filename, confidence, reason = MASTERS_CATEGORIES[degree]
        reasoning.append(reason)
        return CategorizationResult(
            self.data_dir / "masters" / filename,
            confidence,
            "masters",
            reasoning,
            {"degree_type": degree},
        )

    def _is_icas(self, prefix: str, course_code: str) -> bool:
        return prefix in ICAS_PREFIXES or (
            prefix.startswith("I") and prefix not in {"ICE", "ICT", "IND", "INF"}
        )

    def _check_first_year(
        self, course_code: str, prefix: str, reasoning: List[str]
    ) -> Optional[CategorizationResult]:
        if CSS_PREFIX_PATTERN.match(course_code) or prefix == "CSS":
            result_args = (
                "cs_stream.json",
                0.95,
                "first_year_cs",
                "cs",
                "CSS prefix = CS Stream (2024+)",
            )
        elif CS_STREAM_PATTERN.match(course_code):
            result_args = (
                "cs_stream.json",
                0.9,
                "first_year_cs",
                "cs",
                f"CS Stream pattern matched: {course_code}",
            )
        elif CORE_STREAM_PATTERN.match(course_code):
            result_args = (
                "non_cs_stream.json",
                0.9,
                "first_year_core",
                "core",
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

    def _get_semester_from_code(self, code: str) -> Optional[int]:
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
