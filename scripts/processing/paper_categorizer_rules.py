"""Categorization result type and course-code routing rules."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CategorizationResult:
    """Result of categorizing a single paper."""

    target_file: Optional[Path]
    confidence: float
    category: str  # 'btech_branch', 'first_year_cs', 'first_year_core', 'masters', 'bsc', 'other', 'uncertain'
    reasoning: List[str] = field(default_factory=list)
    metadata_filled: Dict[str, Any] = field(default_factory=dict)

    @property
    def should_auto_write(self) -> bool:
        """Papers with >=0.85 confidence are auto-written."""
        return self.confidence >= 0.85


# Course code prefix to branch mapping
PREFIX_TO_BRANCH = {
    "AAE": "Aeronautical",
    "BME": "Biomedical",
    "BIO": "Biotechnology",
    "CHE": "Chemical",
    "CIV": "Civil",
    "CSE": "CSE",
    "DSE": "CSE",  # Data Science -> CSE
    "ECE": "ECE",
    "EEE": "EEE",
    "ELE": "EEE",  # Electrical -> EEE
    "ICE": "EIE",
    "ICT": "CSE",  # ICT -> CSE
    "IND": "Industrial",
    "INF": "IT",
    "MEC": "Mechanical",
    "MME": "Mechanical",  # Mechanical Manufacturing
    "MTE": "Mechatronics",
    "MED": "MediaPrint",
    "CSS": "CSE",  # 2024+ CS Stream new prefix
}

# First year prefixes (Core stream - 2022-2023 all branches, 2024+ non-CS only)
FIRST_YEAR_CORE_PREFIXES = {
    "MAT",
    "PHY",
    "CHM",
    "HUM",
    "CIE",
    "MME",
    "IPE",
    "BIO",
    "EEE",
    "ELE",
}

# First year prefixes (CS stream - 2024+ only)
FIRST_YEAR_CS_PREFIXES = {"MAT", "PHY", "CHM", "HUM", "CIV", "MME", "CSS", "ECE", "ELE"}

# CS Stream (2024+): Codes ending in 0X (01, 02, 03, etc.) in first year
# Examples: MAT1102, PHY1002, CSS1001, CSS1011, ECE1002, HUM1001
CS_STREAM_PATTERN = re.compile(r"^[A-Z]{2,3}1[0-2]0[0-9]$")

# CSS prefix is ALWAYS CS stream (2024+ only)
CSS_PREFIX_PATTERN = re.compile(r"^CSS\d{4}$")

# Core Stream (Non-CS): Codes ending in 71/72 pattern
# Examples: MAT1171, MAT1271, PHY1071, CSE1071, HUM1071, EEE1071
CORE_STREAM_PATTERN = re.compile(r"^[A-Z]{2,3}1[0-2]7[12]$")

# ICAS (B.Sc) pattern - starts with I but not ICE, ICT, IND, INF
ICAS_PREFIXES = {"ICS", "IMA", "IPH", "ICH", "IBI"}  # ICAS-specific prefixes

# Course-code digit mapping used by _get_semester_from_code.
# Key: (year digit, semester-type digit). Masters-level year digit 5 maps to None.
SEMESTER_BY_CODE_DIGITS = {
    (1, 0): 1,
    (1, 1): 1,
    (1, 2): 2,
    (1, 7): 1,
    (2, 1): 3,
    (2, 2): 4,
    (3, 1): 5,
    (3, 2): 6,
    **{(4, sem_type): 7 if sem_type < 2 else 8 for sem_type in range(10)},
}
