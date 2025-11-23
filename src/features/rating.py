"""Simplified Elo-style rating for athletes."""
from __future__ import annotations

from typing import List

import pandas as pd

DEFAULT_RATING = 1500
K_FACTOR = 24


def _expected_score(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def update_ratings(df: pd.DataFrame) -> pd.DataFrame:
    """Update athlete ratings sequentially based on head-to-head ranks."""

    if df.empty:
        return df

    work = df.copy()
    if "race_date_parsed" in work.columns:
        work = work.sort_values("race_date_parsed")
    work["rank_numeric"] = pd.to_numeric(work.get("rank"), errors="coerce")

    ratings: dict[str, float] = {}
    history: List[dict] = []

    for _, group in work.groupby("race_id"):
        group = group.sort_values("rank_numeric")
        athletes = [row["athlete_canonical"] or row["athlete"] for _, row in group.iterrows()]

        for i, athlete in enumerate(athletes):
            if athlete not in ratings:
                ratings[athlete] = DEFAULT_RATING

            for other in athletes:
                if other == athlete:
                    continue
                if other not in ratings:
                    ratings[other] = DEFAULT_RATING

                expected = _expected_score(ratings[athlete], ratings[other])
                actual = 1.0 if i < athletes.index(other) else 0.0
                ratings[athlete] += K_FACTOR * (actual - expected)

            history.append({
                "race_id": group["race_id"].iloc[0],
                "athlete_canonical": athlete,
                "elo_rating": ratings[athlete],
            })

    return pd.DataFrame(history)
