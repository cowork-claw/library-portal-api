import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.config_v2 import settings
from scripts.processing.paper_categorizer import (
    AUTO_WRITE_CONFIDENCE,
    PaperCategorizer,
    _write_paper_to_file,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
STAGING_FILE = settings.STAGING_DIRECTORY / "pending_review.json"


class StagingHandler:
    def __init__(self, staging_file: Path):
        self.staging_file = staging_file
        self.staging_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        try:
            self.data = json.loads(self.staging_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.data = self._empty_data()
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Error loading staging file, creating new: {e}")
            self.data = self._empty_data()

    def _empty_data(self) -> dict[str, Any]:
        return {
            "created_at": datetime.now().isoformat(),
            "description": "Papers needing manual review due to low categorization confidence",
            "papers": [],
        }

    def _save(self) -> None:
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.staging_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved {len(self.data['papers'])} staged papers")

    def _add_paper(
        self,
        paper: dict[str, Any],
        confidence: float,
        reasoning: list[str],
        suggested_target: str | None = None,
    ) -> None:
        if (url := paper.get("url")) and any(
            existing.get("paper", {}).get("url") == url
            for existing in self.data["papers"]
        ):
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
            "extractable_info": {
                "course_code": paper.get("course_code") or paper.get("subject_code"),
                "course_name": paper.get("course_name") or paper.get("subject_name"),
                "year": paper.get("year"),
                "semester": paper.get("semester"),
                "program": paper.get("program"),
                "degree_type": paper.get("degree_type"),
                "file_name": paper.get("file_name"),
                "url": paper.get("url"),
                "path": paper.get("path"),
            },
        }

        self.data["papers"].append(staged)
        self._save()
        logger.info(
            f"Staged paper for review: {paper.get('course_code', 'UNKNOWN')} "
            f"(confidence: {confidence:.2f})"
        )


def _process_paper(
    paper: dict,
    index: int,
    total: int,
    categorizer: PaperCategorizer,
    staging_handler: StagingHandler,
    dry_run: bool,
    stats: dict,
) -> None:
    result = categorizer._categorize(paper)
    by_category = stats["by_category"]
    by_category[result.category] = by_category.get(result.category, 0) + 1

    course_code = paper.get("course_code", "UNKNOWN")
    logger.debug(
        "[%d/%d] %s: %s (conf: %.2f)",
        index,
        total,
        course_code,
        result.category,
        result.confidence,
    )

    if result.confidence >= AUTO_WRITE_CONFIDENCE and result.target_file:
        if dry_run:
            logger.info(
                "DRY RUN: Would write %s to %s", course_code, result.target_file
            )
            stats["auto_written"] += 1
            return

        for key, value in result.metadata_filled.items():
            if key not in paper or paper[key] is None:
                paper[key] = value
        if _write_paper_to_file(paper, result.target_file):
            stats["auto_written"] += 1
        else:
            stats["skipped_duplicate"] += 1
        return

    if dry_run:
        logger.info(
            "DRY RUN: Would stage %s (conf: %.2f)", course_code, result.confidence
        )
    else:
        staging_handler._add_paper(
            paper, result.confidence, result.reasoning, result.target_file
        )
    stats["staged"] += 1


def _log_summary(stats: dict, dry_run: bool, staging_handler: StagingHandler) -> None:
    logger.info("=" * 60)
    logger.info("CATEGORIZATION COMPLETE")
    logger.info("  Total papers: %s", stats["total"])
    logger.info("  Auto-written: %s", stats["auto_written"])
    logger.info("  Staged for review: %s", stats["staged"])
    logger.info("  Skipped (duplicate): %s", stats["skipped_duplicate"])
    logger.info("  Errors: %s", stats["errors"])
    logger.info("By category:")
    for category, count in sorted(stats["by_category"].items()):
        logger.info("  - %s: %s", category, count)
    logger.info("=" * 60)

    if dry_run:
        return

    papers = staging_handler.data.get("papers", ())
    pending_review = sum(not paper.get("reviewed", False) for paper in papers)
    if pending_review > 0:
        logger.warning("%s papers need manual review", pending_review)
        logger.info("   See: %s", STAGING_FILE)


def _run_categorizer(input_file: Path, dry_run: bool = False) -> dict:
    logger.info("Loading papers from: %s", input_file)
    papers = json.loads(input_file.read_text(encoding="utf-8"))

    if not isinstance(papers, list):
        logger.error("Input file must contain a list of papers")
        return {"error": "Invalid input format"}

    logger.info("Loaded %d papers to categorize", len(papers))

    categorizer = PaperCategorizer(settings.DATA_DIRECTORY, STAGING_FILE.parent)
    staging_handler = StagingHandler(STAGING_FILE)
    stats = {
        "total": len(papers),
        "auto_written": 0,
        "staged": 0,
        "skipped_duplicate": 0,
        "errors": 0,
        "by_category": {},
    }

    for index, paper in enumerate(papers, 1):
        try:
            _process_paper(
                paper, index, len(papers), categorizer, staging_handler, dry_run, stats
            )
        except Exception as e:
            logger.error("Error processing paper %d: %s", index, e)
            stats["errors"] += 1

    _log_summary(stats, dry_run, staging_handler)
    return stats


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Categorize scraped papers into organized folder structure"
    )
    parser.add_argument(
        "input", type=Path, help="Input JSON file containing scraped papers"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    stats = _run_categorizer(args.input, dry_run=args.dry_run)

    if stats.get("errors", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    _main()
