"""Feature helpers for athlete form based on recent races."""
from __future__ import annotations

from typing import List

import pandas as pd


def recent_rank_average(df: pd.DataFrame, *, window: int = 5) -> pd.DataFrame:
    """Compute rolling average rank per athlete, sorted by race date if available."""

    if df.empty:
        return df

    work = df.copy()
    if "race_date_parsed" in work.columns:
        work = work.sort_values("race_date_parsed")

    work["rank_numeric"] = pd.to_numeric(work.get("rank"), errors="coerce")

    features: List[pd.DataFrame] = []
    for athlete, group in work.groupby("athlete_canonical"):
        group = group.sort_values("race_date_parsed") if "race_date_parsed" in group else group
        group["recent_rank_avg"] = group["rank_numeric"].rolling(window, min_periods=1).mean()
        features.append(group[["race_id", "athlete_canonical", "recent_rank_avg"]])

    return pd.concat(features, ignore_index=True) if features else pd.DataFrame()


def last_finish_position(df: pd.DataFrame) -> pd.DataFrame:
    """Return the last known finish rank per athlete before each race."""

    if df.empty:
        return df

    work = df.copy()
    work["rank_numeric"] = pd.to_numeric(work.get("rank"), errors="coerce")
    if "race_date_parsed" in work.columns:
        work = work.sort_values("race_date_parsed")

    records: List[dict] = []
    last_rank: dict[str, float] = {}
    for _, row in work.iterrows():
        athlete = row.get("athlete_canonical") or row.get("athlete")
        records.append({
            "race_id": row.get("race_id"),
            "athlete_canonical": athlete,
            "last_rank": last_rank.get(athlete),
        })
        rank_val = row.get("rank_numeric")
        if pd.notna(rank_val):
            last_rank[athlete] = float(rank_val)

    return pd.DataFrame(records)
