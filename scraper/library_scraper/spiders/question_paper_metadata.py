"""Metadata extraction helpers for scraped question-paper PDFs."""

import re
from datetime import datetime

PROGRAM_NAMES = (
    "B.Tech",
    "M.Tech",
    "B.Sc",
    "M.Sc",
    "MBA",
    "MCA",
    "B.Com",
    "M.Com",
    "BBA",
    "BCA",
)


class QuestionPaperMetadataMixin:
    """Extract year, program, semester, and subject metadata from PDF items."""

    def _extract_metadata(self, item):
        """Extract year, semester, program, and subject from item data."""
        path_parts = item["path"].split("/")
        file_name = item["file_name"]

        item["year"] = self._extract_year(path_parts, file_name)
        if not item["year"]:
            self.logger.warning(
                f"Could not extract valid year from path: {item['path']}"
            )

        program = self._extract_program(path_parts)
        if program:
            item["program"] = program

        semester = self._extract_semester(path_parts)
        if semester:
            item["semester"] = semester

        item["subject"] = self._extract_subject(file_name)

    def _extract_year(self, path_parts, file_name):
        """Extract a valid year from the first path component."""
        if not path_parts:
            return None

        potential_year = path_parts[0].strip()
        current_year = datetime.now().year
        if potential_year.isdigit() and len(potential_year) == 4:
            if self._is_valid_year(potential_year, current_year):
                return potential_year
            self.logger.warning(
                f"Year {int(potential_year)} outside valid range for paper: {file_name}"
            )
            return None

        year_match = re.search(r"\b(20\d{2})\b", potential_year)
        if year_match and self._is_valid_year(year_match.group(1), current_year):
            return year_match.group(1)
        return None

    def _is_valid_year(self, year_text, current_year):
        """Return whether a scraped year is within the accepted range."""
        year_int = int(year_text)
        return 2005 <= year_int <= current_year + 1

    def _extract_program(self, path_parts):
        """Extract the first known program component from a path."""
        for part in path_parts:
            if any(program in part for program in PROGRAM_NAMES):
                return part
        return None

    def _extract_semester(self, path_parts):
        """Extract semester text from path components."""
        for part in path_parts:
            sem_match = re.search(r"(I+|[1-9])\s*(st|nd|rd|th)?\s*[Ss]em", part)
            if sem_match:
                return sem_match.group()
        return None

    def _extract_subject(self, file_name):
        """Extract the display subject from a PDF file name."""
        subject = re.sub(r"\.pdf$", "", file_name, flags=re.IGNORECASE)
        subject_match = re.search(r"^([^(\[]+)", subject)
        return subject_match.group(1).strip() if subject_match else subject
