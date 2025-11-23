"""Lightweight helpers for canonicalizing and matching athlete names."""
from __future__ import annotations

import unicodedata
from typing import Iterable, List, Optional, Tuple

from fuzzywuzzy import process


def canonicalize_name(name: str) -> str:
    """Lowercase, strip, and remove accents/punctuation for stable comparisons."""

    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = " ".join(normalized.replace("-", " ").split())
    return normalized.lower().strip()


def best_match(query: str, candidates: Iterable[str], *, threshold: int = 90) -> Optional[Tuple[str, int]]:
    """Return the best fuzzy match above ``threshold`` using fuzzywuzzy ratios."""

    choices: List[str] = list(candidates)
    if not choices:
        return None

    match, score = process.extractOne(query, choices)
    if score >= threshold:
        return match, score
    return None


def deduplicate_names(names: Iterable[str], *, threshold: int = 92) -> List[str]:
    """Collapse near-duplicate names preserving the first occurrence order."""

    seen: List[str] = []
    canon_to_rep: dict[str, str] = {}

    for name in names:
        canon = canonicalize_name(name)
        if canon in canon_to_rep:
            continue

        match = best_match(canon, canon_to_rep.keys(), threshold=threshold)
        if match:
            continue

        canon_to_rep[canon] = name
        seen.append(name)

    return seen
