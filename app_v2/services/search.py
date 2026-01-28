"""
Search Service for Library Portal API V2

Provides fuzzy search functionality for finding papers.
"""

import re
from typing import List, Dict, Any
from thefuzz import fuzz


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
    results = []

    for paper in papers:
        score = _calculate_relevance(paper, query)
        if score > 0:
            results.append((paper, score))

    # Sort by relevance score (highest first)
    results.sort(key=lambda x: x[1], reverse=True)

    return [paper for paper, score in results if score >= threshold]


def _calculate_relevance(paper: Dict[str, Any], query: str) -> float:
    """
    Calculate relevance score for a paper against a query.

    Returns:
        Score between 0 and 1, higher is more relevant
    """
    max_score = 0.0
    query_lower = query.lower()

    # Fields to search with their weights
    search_fields = [
        ("course_code", 1.0),  # Exact course code match is highest priority
        ("course_name", 0.9),
        ("subject_name", 0.9),
        ("display_title", 0.7),
        ("file_name", 0.5),
    ]

    for field_name, weight in search_fields:
        value = paper.get(field_name)
        if not value:
            continue

        value_lower = str(value).lower()

        # Exact match
        if query_lower == value_lower:
            return 1.0 * weight

        # Contains match
        if query_lower in value_lower:
            # Give higher score for prefix match
            if value_lower.startswith(query_lower):
                score = 0.95 * weight
            else:
                score = 0.8 * weight
            max_score = max(max_score, score)
            continue

        # Fuzzy match using TheFuzz (WRatio handles partial matches better)
        ratio = fuzz.WRatio(query_lower, value_lower) / 100.0
        if ratio > 0.7:
            score = ratio * weight
            max_score = max(max_score, score)

        # Word-level matching
        query_words = set(re.split(r"\W+", query_lower))
        value_words = set(re.split(r"\W+", value_lower))

        if query_words & value_words:  # At least one word matches
            overlap = len(query_words & value_words) / len(query_words)
            score = overlap * 0.7 * weight
            max_score = max(max_score, score)

    return max_score


def get_search_suggestions(
    papers: List[Dict[str, Any]], query: str, max_suggestions: int = 10
) -> List[Dict[str, Any]]:
    """
    Get search suggestions based on partial query.

    Returns:
        List of suggestion dicts with 'text', 'type', and 'score'
    """
    if not query or len(query) < 2:
        return []

    query_lower = query.lower()
    suggestions = []
    seen = set()

    for paper in papers:
        # Course code suggestions
        course_code = paper.get("course_code", "")
        if course_code and course_code.lower() not in seen:
            if query_lower in course_code.lower():
                suggestions.append(
                    {
                        "text": course_code,
                        "type": "course_code",
                        "score": (
                            1.0 if course_code.lower().startswith(query_lower) else 0.8
                        ),
                    }
                )
                seen.add(course_code.lower())

        # Course name suggestions
        course_name = paper.get("course_name", "")
        if course_name and course_name.lower() not in seen:
            if query_lower in course_name.lower():
                suggestions.append(
                    {
                        "text": course_name,
                        "type": "course_name",
                        "score": (
                            0.9 if course_name.lower().startswith(query_lower) else 0.7
                        ),
                    }
                )
                seen.add(course_name.lower())

    # Sort by score and limit
    suggestions.sort(key=lambda x: x["score"], reverse=True)
    return suggestions[:max_suggestions]
