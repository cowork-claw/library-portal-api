"""
Staging Handler for Library Portal V2

Manages papers that need manual review due to low categorization confidence.
Papers are staged in a JSON file with all extractable metadata pre-filled.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class StagedPaper:
    """Paper staged for manual review."""

    paper: Dict[str, Any]
    category_result: Dict[str, Any]
    staged_at: str
    reviewed: bool = False
    review_notes: Optional[str] = None
    final_target: Optional[str] = None


class StagingHandler:
    """
    Handles papers that need manual review.

    Features:
    - Pre-fills all extractable metadata
    - Provides skeleton for manual completion
    - Tracks review status
    """

    def __init__(self, staging_file: Path):
        self.staging_file = staging_file
        self.staging_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        """Load existing staging data."""
        if self.staging_file.exists():
            try:
                with open(self.staging_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Error loading staging file, creating new: {e}")
                self.data = self._empty_data()
        else:
            self.data = self._empty_data()

    def _empty_data(self) -> Dict[str, Any]:
        return {
            "created_at": datetime.now().isoformat(),
            "description": "Papers needing manual review due to low categorization confidence",
            "papers": [],
        }

    def save(self) -> None:
        """Save staging data to file."""
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.staging_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved {len(self.data['papers'])} staged papers")

    def add_paper(
        self,
        paper: Dict[str, Any],
        confidence: float,
        reasoning: List[str],
        suggested_target: Optional[str] = None,
    ) -> None:
        """
        Add a paper to staging for manual review.

        Args:
            paper: The paper dictionary
            confidence: Confidence score (0-1)
            reasoning: List of reasoning strings explaining categorization
            suggested_target: Suggested target file (may be None if uncertain)
        """
        # Check for duplicates by URL
        url = paper.get("url")
        if url:
            for existing in self.data["papers"]:
                if existing.get("paper", {}).get("url") == url:
                    logger.debug(f"Paper already staged: {url}")
                    return

        staged = {
            "paper": paper,
            "categorization": {
                "confidence": confidence,
                "reasoning": reasoning,
                "suggested_target": str(suggested_target) if suggested_target else None,
            },
            "staged_at": datetime.now().isoformat(),
            "reviewed": False,
            "review_notes": None,
            "final_target": None,
            # Pre-filled skeleton for easier review
            "extractable_info": self._extract_info(paper),
        }

        self.data["papers"].append(staged)
        self.save()

        logger.info(
            f"Staged paper for review: {paper.get('course_code', 'UNKNOWN')} "
            f"(confidence: {confidence:.2f})"
        )

    def _extract_info(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and summarize key information for review."""
        return {
            "course_code": paper.get("course_code") or paper.get("subject_code"),
            "course_name": paper.get("course_name") or paper.get("subject_name"),
            "year": paper.get("year"),
            "semester": paper.get("semester"),
            "program": paper.get("program"),
            "degree_type": paper.get("degree_type"),
            "file_name": paper.get("file_name"),
            "url": paper.get("url"),
            "path": paper.get("path"),
        }

    def get_pending_count(self) -> int:
        """Get count of papers pending review."""
        return sum(1 for p in self.data["papers"] if not p.get("reviewed", False))

    def get_pending_papers(self) -> List[Dict[str, Any]]:
        """Get all papers pending review."""
        return [p for p in self.data["papers"] if not p.get("reviewed", False)]

    def mark_reviewed(
        self, url: str, final_target: str, notes: Optional[str] = None
    ) -> bool:
        """
        Mark a staged paper as reviewed.

        Args:
            url: URL of the paper to mark
            final_target: Final target file after manual review
            notes: Optional review notes

        Returns:
            True if paper was found and marked
        """
        for paper in self.data["papers"]:
            if paper.get("paper", {}).get("url") == url:
                paper["reviewed"] = True
                paper["final_target"] = final_target
                paper["review_notes"] = notes
                paper["reviewed_at"] = datetime.now().isoformat()
                self.save()
                return True
        return False

    def clear_reviewed(self) -> int:
        """Remove all reviewed papers from staging. Returns count removed."""
        original = len(self.data["papers"])
        self.data["papers"] = [
            p for p in self.data["papers"] if not p.get("reviewed", False)
        ]
        removed = original - len(self.data["papers"])
        self.save()
        return removed

    def get_stats(self) -> Dict[str, Any]:
        """Get staging statistics."""
        papers = self.data.get("papers", [])
        return {
            "total_staged": len(papers),
            "pending_review": sum(1 for p in papers if not p.get("reviewed", False)),
            "reviewed": sum(1 for p in papers if p.get("reviewed", False)),
            "by_confidence": self._group_by_confidence(papers),
        }

    def _group_by_confidence(self, papers: List[Dict]) -> Dict[str, int]:
        """Group papers by confidence ranges."""
        groups = {"high_0.5+": 0, "medium_0.3-0.5": 0, "low_<0.3": 0}
        for p in papers:
            conf = p.get("categorization", {}).get("confidence", 0)
            if conf >= 0.5:
                groups["high_0.5+"] += 1
            elif conf >= 0.3:
                groups["medium_0.3-0.5"] += 1
            else:
                groups["low_<0.3"] += 1
        return groups
