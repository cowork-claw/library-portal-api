"""Fuzzy search service for paper metadata."""

import re
from typing import Any, Dict, List, Optional, Set

from thefuzz import fuzz

WORD_MATCH_SCORE_FACTOR = 0.7
WORD_TOKEN_PATTERN = re.compile(r"\w+")

# Fields to search with their weights
SEARCH_FIELDS = [
    ("course_code", 1.0),  # Exact course code match is highest priority
    ("course_name", 0.9),
    ("subject_name", 0.9),
    ("display_title", 0.7),
    ("file_name", 0.5),
]


def _tokenize_words(text: str) -> Set[str]:
    return set(WORD_TOKEN_PATTERN.findall(text))


def _search_papers(
    papers: List[Dict[str, Any]], query: str, threshold: float = 0.5
) -> List[Dict[str, Any]]:
    if not query or not papers:
        return papers

    query = query.strip().lower()
    if not query:
        return papers
    query_words = _tokenize_words(query)

    # Guard clause: ensure we filter out zero-score papers even if threshold is 0 or negative
    # unless explicitly desired? No, search generally implies some relevance.
    effective_threshold = max(threshold, 0.01) if threshold <= 0 else threshold

    results = [
        (paper, score)
        for paper in papers
        if (score := _calculate_relevance(paper, query, query_words))
        >= effective_threshold
    ]

    # Sort by relevance score (highest first)
    results.sort(key=lambda x: x[1], reverse=True)

    return [paper for paper, score in results]


def _field_search_data(
    paper: Dict[str, Any], search_meta: Optional[Dict[str, Any]], field_name: str
) -> Optional[tuple[str, Optional[Set[str]]]]:
    if search_meta and (meta := search_meta.get(field_name)):
        return meta["lower"], meta["words"]

    value = paper.get(field_name)
    if not value:
        return None
    return str(value).lower(), None


def _exact_or_contains_score(
    query: str, value_lower: str, weight: float
) -> Optional[float]:
    if query == value_lower:
        return weight
    if query not in value_lower:
        return None
    return (0.95 if value_lower.startswith(query) else 0.8) * weight


def _fuzzy_score(query: str, value_lower: str, weight: float) -> float:
    ratio = fuzz.WRatio(query, value_lower) / 100.0
    if ratio > WORD_MATCH_SCORE_FACTOR:
        return ratio * weight
    return 0.0


def _word_overlap_score(
    query_words: Set[str],
    value_words: Optional[Set[str]],
    value_lower: str,
    weight: float,
) -> float:
    if not query_words:
        return 0.0

    if value_words is None:
        value_words = _tokenize_words(value_lower)

    matching_words = query_words & value_words
    if not matching_words:
        return 0.0
    return (len(matching_words) / len(query_words)) * WORD_MATCH_SCORE_FACTOR * weight


def _calculate_relevance(
    paper: Dict[str, Any], query: str, query_words: Set[str]
) -> float:
    max_score = 0.0
    search_meta = paper.get("_search_meta")

    for field_name, weight in SEARCH_FIELDS:
        if max_score >= weight:
            break

        field_data = _field_search_data(paper, search_meta, field_name)
        if field_data is None:
            continue

        value_lower, value_words = field_data
        phrase_score = _exact_or_contains_score(query, value_lower, weight)
        if phrase_score is not None:
            if phrase_score == weight:
                return phrase_score
            max_score = max(max_score, phrase_score)
            continue

        max_score = max(max_score, _fuzzy_score(query, value_lower, weight))
        if max_score >= WORD_MATCH_SCORE_FACTOR * weight:
            continue

        max_score = max(
            max_score,
            _word_overlap_score(query_words, value_words, value_lower, weight),
        )

    return max_score
