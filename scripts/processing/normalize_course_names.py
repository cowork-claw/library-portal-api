"""Canonicalize ``course_name`` spellings within each ``course_code``.

The scraped data stores many spellings of the same course name (typos, stray
``(MAKEUP)``/``PART A`` suffixes, casing) which fragments filtering/search.
This unifies them *per exact course_code* only:

  * cluster a code's spellings by fuzzy similarity to the dominant (most common)
    spelling,
  * rewrite that cluster to the existing spelling with the fewest misspelled
    words (tie-broken by how common it is for that code). Since every spelling
    of one course shares the same domain vocabulary, only the differing word is
    actually compared, so "Finacial" loses to "Financial",
  * leave genuinely different names (e.g. a mis-coded subject) untouched.

It only ever picks an *existing* spelling, so it cannot invent a new typo. If
``pyspellchecker`` is not installed it falls back to the most common spelling.

Dry-run by default; pass ``--apply`` to write the JSON files back.
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from thefuzz import fuzz

try:
    from spellchecker import SpellChecker

    _SPELL: SpellChecker | None = SpellChecker()
except ImportError:
    _SPELL = None

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "classified" / "organized"
SIMILARITY_THRESHOLD = 88
_PAREN = re.compile(r"\([^)]*\)")
_JUNK = re.compile(r"\b(part\s*[ab]|set\s*\d+|makeup)\b", re.IGNORECASE)
_WS = re.compile(r"\s+")
_WORD = re.compile(r"[a-zA-Z]{2,}")


def _clean(name: str) -> str:
    """Strip parenthetical code/makeup suffixes, stray parens and edge noise."""
    text = _JUNK.sub(" ", _PAREN.sub(" ", name)).replace("(", " ").replace(")", " ")
    return _WS.sub(" ", text).strip(" -_.,")


def _misspelled(name: str) -> int:
    if _SPELL is None:
        return 0
    words = [w.lower() for w in _WORD.findall(name)]
    return len(_SPELL.unknown(words)) if words else 0


def _load() -> tuple[dict[Path, dict], dict[str, list[dict]]]:
    docs: dict[Path, dict] = {}
    by_code: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(DATA_DIR.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        docs[path] = data
        for papers in data.values():
            if not isinstance(papers, list):
                continue
            for paper in papers:
                if (
                    isinstance(paper, dict)
                    and paper.get("course_code")
                    and paper.get("course_name")
                ):
                    by_code[paper["course_code"]].append(paper)
    return docs, by_code


def _canonical(names: Counter) -> str:
    """Pick the cleaned spelling with fewest typos, then most common, then longest."""
    cleaned: Counter = Counter()
    for name, count in names.items():
        if clean := _clean(name):
            cleaned[clean] += count
    return min(cleaned, key=lambda c: (_misspelled(c), -cleaned[c], -len(c)))


def plan(by_code):
    changes, skipped = [], []
    for papers in by_code.values():
        names = Counter(p["course_name"] for p in papers)
        if len(names) <= 1:
            continue
        dominant = names.most_common(1)[0][0]
        matched = Counter(
            {
                n: c
                for n, c in names.items()
                if fuzz.token_set_ratio(_clean(n), _clean(dominant))
                >= SIMILARITY_THRESHOLD
            }
        )
        canonical = _canonical(matched)
        for paper in papers:
            current = paper["course_name"]
            if current not in matched:
                skipped.append((paper["course_code"], current))
            elif current != canonical:
                changes.append((paper, current, canonical))
    return changes, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes to disk")
    args = parser.parse_args()
    if _SPELL is None:
        print("WARNING: pyspellchecker not installed; falling back to most-common.\n")

    docs, by_code = _load()
    changes, skipped = plan(by_code)

    rewrites = Counter((old, new) for _, old, new in changes)
    print(f"Papers to normalize: {len(changes)} across {len(by_code)} course codes")
    for (old, new), count in rewrites.most_common(60):
        print(f"  {count:2d}x  {old!r}\n       -> {new!r}")
    if skipped:
        print(f"\nLeft untouched (dissimilar to dominant name): {len(set(skipped))}")
        for code, name in sorted(set(skipped)):
            print(f"  {code}: {name!r}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write changes.")
        return

    changed_ids = {id(paper) for paper, _, _ in changes}
    for paper, _, new in changes:
        paper["course_name"] = new
    for path, data in docs.items():
        if any(
            isinstance(papers, list) and any(id(p) in changed_ids for p in papers)
            for papers in data.values()
        ):
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    print(f"\nApplied {len(changes)} rewrites.")


if __name__ == "__main__":
    main()
