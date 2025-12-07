"""
Run Categorizer - CLI Entry Point

Process scraped papers and categorize them into the organized folder structure.
High-confidence papers are auto-written, low-confidence papers are staged for review.

Usage:
    python run_categorizer.py <input_json>
    python run_categorizer.py scraped_output.json
"""

import json
import argparse
from pathlib import Path
import logging
import sys

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.processing.paper_categorizer import PaperCategorizer, write_paper_to_file
from scripts.processing.staging_handler import StagingHandler
from scraper.scraper_config import DATA_DIRECTORY, STAGING_FILE, AUTO_WRITE_THRESHOLD

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_categorizer(input_file: Path, dry_run: bool = False) -> dict:
    """
    Categorize papers from input file.

    Args:
        input_file: Path to scraped papers JSON
        dry_run: If True, don't write files, just show what would happen

    Returns:
        Statistics dictionary
    """
    # Load input papers
    logger.info(f"Loading papers from: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        papers = json.load(f)

    if not isinstance(papers, list):
        logger.error("Input file must contain a list of papers")
        return {"error": "Invalid input format"}

    logger.info(f"Loaded {len(papers)} papers to categorize")

    # Initialize categorizer and staging handler
    categorizer = PaperCategorizer(DATA_DIRECTORY, STAGING_FILE.parent)
    staging_handler = StagingHandler(STAGING_FILE)

    # Statistics
    stats = {
        "total": len(papers),
        "auto_written": 0,
        "staged": 0,
        "skipped_duplicate": 0,
        "errors": 0,
        "by_category": {},
        "by_confidence": {"high": 0, "medium": 0, "low": 0},
    }

    # Process each paper
    for i, paper in enumerate(papers, 1):
        try:
            result = categorizer.categorize(paper)

            # Update category stats
            cat = result.category
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

            # Update confidence stats
            if result.confidence >= 0.85:
                stats["by_confidence"]["high"] += 1
            elif result.confidence >= 0.5:
                stats["by_confidence"]["medium"] += 1
            else:
                stats["by_confidence"]["low"] += 1

            # Log progress
            course_code = paper.get("course_code", "UNKNOWN")
            logger.debug(
                f"[{i}/{len(papers)}] {course_code}: "
                f"{result.category} (conf: {result.confidence:.2f})"
            )

            if result.should_auto_write and result.target_file:
                # High confidence - auto-write
                if dry_run:
                    logger.info(
                        f"DRY RUN: Would write {course_code} to {result.target_file}"
                    )
                    stats["auto_written"] += 1
                else:
                    # Merge any auto-filled metadata
                    for key, value in result.metadata_filled.items():
                        if key not in paper or paper[key] is None:
                            paper[key] = value

                    if write_paper_to_file(paper, result.target_file):
                        stats["auto_written"] += 1
                    else:
                        stats["skipped_duplicate"] += 1
            else:
                # Low confidence - stage for review
                if dry_run:
                    logger.info(
                        f"DRY RUN: Would stage {course_code} (conf: {result.confidence:.2f})"
                    )
                else:
                    staging_handler.add_paper(
                        paper, result.confidence, result.reasoning, result.target_file
                    )
                stats["staged"] += 1

        except Exception as e:
            logger.error(f"Error processing paper {i}: {e}")
            stats["errors"] += 1

    # Summary
    logger.info("=" * 60)
    logger.info("CATEGORIZATION COMPLETE")
    logger.info(f"  Total papers: {stats['total']}")
    logger.info(f"  Auto-written: {stats['auto_written']}")
    logger.info(f"  Staged for review: {stats['staged']}")
    logger.info(f"  Skipped (duplicate): {stats['skipped_duplicate']}")
    logger.info(f"  Errors: {stats['errors']}")
    logger.info("By category:")
    for cat, count in sorted(stats["by_category"].items()):
        logger.info(f"  - {cat}: {count}")
    logger.info("=" * 60)

    # Report staging stats
    if not dry_run:
        staging_stats = staging_handler.get_stats()
        if staging_stats["pending_review"] > 0:
            logger.warning(
                f"⚠️  {staging_stats['pending_review']} papers need manual review"
            )
            logger.info(f"   See: {STAGING_FILE}")

    return stats


def main():
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

    stats = run_categorizer(args.input, dry_run=args.dry_run)

    if stats.get("errors", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
