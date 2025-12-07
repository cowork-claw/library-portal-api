"""
Add program_abbrev field to all paper JSON files.
Run from project root: python scripts/add_program_abbrev.py
"""

import json
import re
from pathlib import Path

# Mapping from filename (stem) to abbreviation
FILENAME_TO_ABBREV = {
    "Biomedical": "BME",
    "CSE": "CSE",
    "IT": "IT",
    "ECE": "ECE",
    "EEE": "EEE",
    "EIE": "EIE",
    "Mechanical": "ME",
    "Mechatronics": "MXE",
    "Civil": "CE",
    "Chemical": "CHE",
    "Biotechnology": "BIO",
    "Aeronautical": "AERO",
    "Automobile": "AUTO",
    "Industrial": "INE",
    "MediaPrint": "MPE",
}

# Mapping from full program name to abbreviation
PROGRAM_NAME_TO_ABBREV = {
    "biomedical engineering": "BME",
    "computer science and engineering": "CSE",
    "computer science": "CSE",
    "information technology": "IT",
    "electronics and communication": "ECE",
    "electrical and electronics": "EEE",
    "electronics and instrumentation": "EIE",
    "mechanical engineering": "ME",
    "mechatronics engineering": "MXE",
    "civil engineering": "CE",
    "chemical engineering": "CHE",
    "biotechnology": "BIO",
    "aeronautical engineering": "AERO",
    "automobile engineering": "AUTO",
    "industrial engineering": "INE",
    "media and print engineering": "MPE",
    "computer and communication": "CCE",
    "artificial intelligence": "AIML",
    "data science": "DSE",
    "mathematics and computing": "MnC",
    "m.tech": "M.Tech",
    "m.e": "M.E",
    "mca": "MCA",
}

# Course code prefix to abbreviation (fallback)
CODE_PREFIX_TO_ABBREV = {
    "BME": "BME",
    "CSE": "CSE",
    "ECE": "ECE",
    "EEE": "EEE",
    "EIE": "EIE",
    "MEE": "ME",
    "MEC": "ME",
    "MXE": "MXE",
    "CVE": "CE",
    "CHE": "CHE",
    "BIO": "BIO",
    "AER": "AERO",
    "AUT": "AUTO",
    "INE": "INE",
    "MPE": "MPE",
    "CCE": "CCE",
    "AIL": "AIML",
    "DSE": "DSE",
    "MNC": "MnC",
    "MAT": "MnC",
    "ITE": "IT",
    "INT": "IT",
    "MTX": "M.Tech",
    "MTH": "M.Tech",
    "MCA": "MCA",
}


def derive_abbrev(paper: dict, filename_abbrev: str | None) -> str:
    """Derive program abbreviation from paper data."""

    # Priority 1: Use filename-based abbreviation
    if filename_abbrev:
        return filename_abbrev

    # Priority 2: Match program/specialization field
    program = paper.get("program") or paper.get("specialization") or ""
    if program:
        for name, abbrev in PROGRAM_NAME_TO_ABBREV.items():
            if name in program.lower():
                return abbrev

    # Priority 3: Extract from course code prefix
    course_code = paper.get("course_code") or paper.get("subject_code") or ""
    if course_code:
        prefix = re.match(r"^([A-Z]{3})", course_code.upper())
        if prefix:
            return CODE_PREFIX_TO_ABBREV.get(prefix.group(1), prefix.group(1))

    # Priority 4: Check valid_for_branches if available
    curriculum_context = paper.get("curriculum_context")
    if curriculum_context and curriculum_context.get("valid_for_branches"):
        branches = curriculum_context["valid_for_branches"]
        if branches and isinstance(branches, list) and len(branches) > 0:
            return branches[0]

    # Fallback: Unknown
    return "UNKNOWN"


def process_file(json_path: Path, filename_abbrev: str | None) -> tuple[int, int]:
    """Process a single JSON file. Returns (papers_updated, errors)."""

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated = 0
    errors = 0

    for course_code, papers in data.items():
        if not isinstance(papers, list):
            continue

        for paper in papers:
            try:
                # Add program_abbrev field
                abbrev = derive_abbrev(paper, filename_abbrev)
                paper["program_abbrev"] = abbrev

                # Fix valid_for_branches if null
                if paper.get("curriculum_context"):
                    if paper["curriculum_context"].get("valid_for_branches") is None:
                        paper["curriculum_context"]["valid_for_branches"] = [abbrev]

                updated += 1
            except Exception as e:
                print(f"Error processing paper in {json_path}: {e}")
                errors += 1

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return updated, errors


def main():
    data_dir = Path("data/classified/organized")

    total_updated = 0
    total_errors = 0

    # Process btech/branches (use filename mapping)
    branches_dir = data_dir / "btech" / "branches"
    if branches_dir.exists():
        for json_file in sorted(branches_dir.glob("*.json")):
            filename_abbrev = FILENAME_TO_ABBREV.get(json_file.stem)
            updated, errors = process_file(json_file, filename_abbrev)
            print(
                f"[btech/branches/{json_file.name}] Updated: {updated}, Errors: {errors}"
            )
            total_updated += updated
            total_errors += errors

    # Process btech/first_year (no filename mapping, derive from course code)
    first_year_dir = data_dir / "btech" / "first_year"
    if first_year_dir.exists():
        for json_file in sorted(first_year_dir.glob("*.json")):
            updated, errors = process_file(json_file, None)
            print(
                f"[btech/first_year/{json_file.name}] Updated: {updated}, Errors: {errors}"
            )
            total_updated += updated
            total_errors += errors

    # Process btech/common_electives.json
    common_electives = data_dir / "btech" / "common_electives.json"
    if common_electives.exists():
        updated, errors = process_file(common_electives, None)
        print(f"[btech/common_electives.json] Updated: {updated}, Errors: {errors}")
        total_updated += updated
        total_errors += errors

    # Process masters (mtech, me, mca)
    masters_dir = data_dir / "masters"
    if masters_dir.exists():
        for json_file in sorted(masters_dir.glob("*.json")):
            updated, errors = process_file(json_file, None)
            print(f"[masters/{json_file.name}] Updated: {updated}, Errors: {errors}")
            total_updated += updated
            total_errors += errors

    # Process bsc
    bsc_dir = data_dir / "bsc"
    if bsc_dir.exists():
        for json_file in sorted(bsc_dir.glob("*.json")):
            updated, errors = process_file(json_file, None)
            print(f"[bsc/{json_file.name}] Updated: {updated}, Errors: {errors}")
            total_updated += updated
            total_errors += errors

    # Process other.json
    other_json = data_dir / "other.json"
    if other_json.exists():
        updated, errors = process_file(other_json, None)
        print(f"[other.json] Updated: {updated}, Errors: {errors}")
        total_updated += updated
        total_errors += errors

    print(f"\n=== COMPLETE ===")
    print(f"Total papers updated: {total_updated}")
    print(f"Total errors: {total_errors}")


if __name__ == "__main__":
    main()
