"""Utility helpers for parsing and formatting race times and gaps."""
from __future__ import annotations

import datetime as _dt
import math
from typing import Optional, Tuple


def _clean_time_string(value: str) -> str:
    """Normalize delimiters and trim whitespace."""

    cleaned = value.strip().replace(",", ".")
    cleaned = cleaned.replace("'", ":")
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    return cleaned


def parse_time_to_seconds(value: Optional[str]) -> Optional[float]:
    """Convert a race time string (e.g., ``1:23:45.6`` or ``3:15.2``) to seconds.

    Returns ``None`` when the input is missing or cannot be parsed.
    """

    if value is None:
        return None

    cleaned = _clean_time_string(value)
    if not cleaned or cleaned.lower() in {"dns", "dnf", "dsq", "nan", "-"}:
        return None

    parts = cleaned.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            total_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            total_seconds = int(minutes) * 60 + float(seconds)
        else:
            total_seconds = float(parts[0])
    except ValueError:
        return None

    return float(total_seconds)


def parse_gap(value: Optional[str]) -> Optional[float]:
    """Parse a time gap string into seconds (e.g., ``+12.3`` -> ``12.3``)."""

    if value is None:
        return None

    cleaned = _clean_time_string(value).lstrip("+-")
    if not cleaned:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return parse_time_to_seconds(cleaned)


def format_seconds(seconds: Optional[float]) -> Optional[str]:
    """Format seconds back into ``H:MM:SS.s`` if possible."""

    if seconds is None or not math.isfinite(seconds):
        return None

    seconds = float(seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remainder = seconds % 60

    if hours:
        return f"{hours}:{minutes:02d}:{remainder:04.1f}" if remainder % 1 else f"{hours}:{minutes:02d}:{int(remainder):02d}"
    return f"{minutes}:{remainder:04.1f}" if remainder % 1 else f"{minutes}:{int(remainder):02d}"


def infer_race_date(value: Optional[str]) -> Optional[_dt.date]:
    """Attempt to parse race date strings in common formats."""

    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d.%m.%y"):
        try:
            return _dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def split_timestamp(value: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[float]]:
    """Break a timestamp into hours, minutes, and seconds for analysis."""

    total_seconds = parse_time_to_seconds(value)
    if total_seconds is None:
        return None, None, None

    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    return hours, minutes, seconds
