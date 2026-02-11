"""
Search Service for Library Portal API V2

Provides fuzzy search functionality for finding papers.
"""

import re
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from thefuzz import fuzz

WORD_MATCH_SCORE_FACTOR = 0.7
WORD_TOKEN_PATTERN = re.compile(r"\w+")


def _tokenize_words(text: str) -> Set[str]:
    return set(WORD_TOKEN_PATTERN.findall(text))


def _get_search_meta(
    paper: Dict[str, Any],
    search_meta_by_url: Optional[Mapping[str, Dict[str, Dict[str, Any]]]],
) -> Optional[Dict[str, Dict[str, Any]]]:
    search_meta = paper.get("_search_meta")
    if search_meta is not None:
        return search_meta
    if not search_meta_by_url:
        return None
    paper_url = paper.get("url")
    if not paper_url:
        return None
    return search_meta_by_url.get(paper_url)


def _resolve_search_values(
    paper: Dict[str, Any],
    field_name: str,
    search_meta: Optional[Dict[str, Dict[str, Any]]],
) -> Optional[Tuple[str, Optional[Set[str]]]]:
    if search_meta and (meta := search_meta.get(field_name)):
        return meta["lower"], meta["words"]
    value = paper.get(field_name)
    if not value:
        return None
    return str(value).lower(), None


def search_papers(
    papers: List[Dict[str, Any]],
    query: str,
    threshold: float = 0.4,
    search_meta_by_url: Optional[Mapping[str, Dict[str, Dict[str, Any]]]] = None,
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
    results = []

    for paper in papers:
        score = _calculate_relevance(paper, query, query_words, search_meta_by_url)
        if score > 0:
            results.append((paper, score))

    # Sort by relevance score (highest first)
    results.sort(key=lambda x: x[1], reverse=True)

    return [paper for paper, score in results if score >= threshold]


def _calculate_relevance(
    paper: Dict[str, Any],
    query: str,
    query_words: Set[str],
    search_meta_by_url: Optional[Mapping[str, Dict[str, Dict[str, Any]]]] = None,
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

    search_meta = _get_search_meta(paper, search_meta_by_url)

    for field_name, weight in search_fields:
        # Use pre-computed values if available (fast path).
        # Fallback computes values directly from paper fields.
        values = _resolve_search_values(paper, field_name, search_meta)
        if values is None:
            continue
        value_lower, value_words = values

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
