"""
Search Service for Library Portal API V2

Provides fuzzy search functionality for finding papers.
"""

from typing import Any, Dict, List, Set

from thefuzz import fuzz

from app_v2.utils import WORD_TOKEN_PATTERN

WORD_MATCH_SCORE_FACTOR = 0.7


def _tokenize_words(text: str) -> Set[str]:
    return set(WORD_TOKEN_PATTERN.findall(text))


def search_papers(
    papers: List[Dict[str, Any]], query: str, threshold: float = 0.4
) -> List[Dict[str, Any]]:
    """
    Search papers using fuzzy matching.

    Searches across:
    - course_code
    - course_name
    - subject_name
    - display_title
    - file_name

    Args:
        papers: List of paper dictionaries to search
        query: Search query string
        threshold: Minimum similarity score (0-1) to include in results

    Returns:
        List of matching papers, sorted by relevance
    """
    if not query or not papers:
        return papers

    query = query.strip().lower()
    query_words = _tokenize_words(query)

    # Calculate relevance for all papers
    results = [
        (paper, score)
        for paper in papers
        if (score := _calculate_relevance(paper, query, query_words)) > 0
    ]

    # Sort by relevance score (highest first)
    results.sort(key=lambda x: x[1], reverse=True)

    return [paper for paper, score in results if score >= threshold]


def _calculate_relevance(
    paper: Dict[str, Any], query: str, query_words: Set[str]
) -> float:
    """
    Calculate relevance score for a paper against a query.

    Returns:
        Score between 0 and 1, higher is more relevant
    """
    max_score = 0.0

    # Fields to search with their weights
    search_fields = [
        ("course_code", 1.0),  # Exact course code match is highest priority
        ("course_name", 0.9),
        ("subject_name", 0.9),
        ("display_title", 0.7),
        ("file_name", 0.5),
    ]

    search_meta = paper.get("_search_meta")

    for field_name, weight in search_fields:
        # Optimization: Early exit if max_score is already higher than
        # current field's max potential
        if max_score >= weight:
            break

        # Use pre-computed values if available (fast path)
        if search_meta and (meta := search_meta.get(field_name)):
            value_lower = meta["lower"]
            value_words = meta["words"]
        else:
            # Fallback for papers not yet indexed with meta or missing fields
            value = paper.get(field_name)
            if not value:
                continue
            value_lower = str(value).lower()
            value_words = None  # Computed only if needed

        # Exact match
        if query == value_lower:
            return 1.0 * weight

        # Contains match
        if query in value_lower:
            # Give higher score for prefix match
            if value_lower.startswith(query):
                score = 0.95 * weight
            else:
                score = 0.8 * weight
            max_score = max(max_score, score)
            continue

        # Fuzzy match using TheFuzz (WRatio handles partial matches better)
        ratio = fuzz.WRatio(query, value_lower) / 100.0
        if ratio > WORD_MATCH_SCORE_FACTOR:
            score = ratio * weight
            max_score = max(max_score, score)

        # Optimization: Skip word matching if fuzzy match was already very strong
        # Word match max score is 0.7 * weight. If max_score is already higher,
        # word matching cannot improve the result.
        if max_score >= WORD_MATCH_SCORE_FACTOR * weight:
            continue

        # Word-level matching
        if value_words is None:
            value_words = _tokenize_words(value_lower)

        if query_words and (query_words & value_words):  # At least one word matches
            overlap = len(query_words & value_words) / len(query_words)
            score = overlap * WORD_MATCH_SCORE_FACTOR * weight
            max_score = max(max_score, score)

    return max_score
