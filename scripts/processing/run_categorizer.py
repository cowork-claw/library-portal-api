"""Categorize scraped papers from the command line."""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scraper.scraper_config import DATA_DIRECTORY, STAGING_FILE
from scripts.processing.paper_categorizer import PaperCategorizer, write_paper_to_file
from scripts.processing.paper_categorizer_rules import AUTO_WRITE_CONFIDENCE
from scripts.processing.staging_handler import StagingHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _new_stats(total: int) -> dict:
    """Create the summary dictionary used by the categorizer run."""
    return {
        "total": total,
        "auto_written": 0,
        "staged": 0,
        "skipped_duplicate": 0,
        "errors": 0,
        "by_category": {},
        "by_confidence": {"high": 0, "medium": 0, "low": 0},
    }


def _record_result(stats: dict, category: str, confidence: float) -> None:
    """Update category and confidence counters for one categorization result."""
    stats["by_category"][category] = stats["by_category"].get(category, 0) + 1

    if confidence >= AUTO_WRITE_CONFIDENCE:
        stats["by_confidence"]["high"] += 1
    elif confidence >= 0.5:
        stats["by_confidence"]["medium"] += 1
    else:
        stats["by_confidence"]["low"] += 1


def _merge_metadata(paper: dict, metadata: dict) -> None:
    """Fill missing paper metadata discovered by the categorizer."""
    for key, value in metadata.items():
        if key not in paper or paper[key] is None:
            paper[key] = value


def _handle_auto_write(paper: dict, result, dry_run: bool, stats: dict) -> None:
    """Write a high-confidence paper or count the dry-run action."""
    course_code = paper.get("course_code", "UNKNOWN")
    if dry_run:
        logger.info("DRY RUN: Would write %s to %s", course_code, result.target_file)
        stats["auto_written"] += 1
        return

    _merge_metadata(paper, result.metadata_filled)
    if write_paper_to_file(paper, result.target_file):
        stats["auto_written"] += 1
    else:
        stats["skipped_duplicate"] += 1


def _handle_staging(
    paper: dict, result, dry_run: bool, stats: dict, staging_handler
) -> None:
    """Stage a low-confidence paper or count the dry-run action."""
    course_code = paper.get("course_code", "UNKNOWN")
    if dry_run:
        logger.info(
            "DRY RUN: Would stage %s (conf: %.2f)", course_code, result.confidence
        )
    else:
        staging_handler._add_paper(
            paper, result.confidence, result.reasoning, result.target_file
        )
    stats["staged"] += 1


def _process_paper(
    paper: dict,
    index: int,
    total: int,
    categorizer: PaperCategorizer,
    staging_handler: StagingHandler,
    dry_run: bool,
    stats: dict,
) -> None:
    """Categorize one paper and route it to writing or staging."""
    result = categorizer.categorize(paper)
    _record_result(stats, result.category, result.confidence)

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
        _handle_auto_write(paper, result, dry_run, stats)
    else:
        _handle_staging(paper, result, dry_run, stats, staging_handler)


def _log_summary(stats: dict, dry_run: bool, staging_handler: StagingHandler) -> None:
    """Log the categorization run summary."""
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

    staging_stats = staging_handler._get_stats()
    if staging_stats["pending_review"] > 0:
        logger.warning("%s papers need manual review", staging_stats["pending_review"])
        logger.info("   See: %s", STAGING_FILE)


def _run_categorizer(input_file: Path, dry_run: bool = False) -> dict:
    """Categorize papers from an input JSON file."""
    logger.info("Loading papers from: %s", input_file)
    with open(input_file, "r", encoding="utf-8") as f:
        papers = json.load(f)

    if not isinstance(papers, list):
        logger.error("Input file must contain a list of papers")
        return {"error": "Invalid input format"}

    logger.info("Loaded %d papers to categorize", len(papers))

    categorizer = PaperCategorizer(DATA_DIRECTORY, STAGING_FILE.parent)
    staging_handler = StagingHandler(STAGING_FILE)
    stats = _new_stats(len(papers))

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
