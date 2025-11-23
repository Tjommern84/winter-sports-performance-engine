"""Parse raw FirstSkiSport scraper outputs into structured tables.

The scraper writes raw JSON files under ``data_raw/firstskisport`` with the
structure::

    {
        "url": "...",
        "metadata": {"title": ..., "date": ..., ...},
        "results": [
            {"rank": "1", "athlete": "...", "nation": "...", ...},
            ...
        ],
    }

This module turns each JSON file into a tidy pandas ``DataFrame`` with race
metadata repeated for every athlete row. Outputs are written to
``data_clean/firstskisport`` by default, either as Parquet or CSV.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urlparse

import pandas as pd

logger = logging.getLogger(__name__)


# ----------------------------- Utility functions -----------------------------


def _normalize_column(name: str) -> str:
    """Convert a column header to snake_case-ish form."""

    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "column"


def _extract_race_id(path: Path, payload: Dict[str, object]) -> str:
    """Infer race ID from URL query parameters or fallback to filename stem."""

    url = str(payload.get("url", ""))
    if url:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        for key in ("raceid", "race", "id"):
            if key in query and query[key]:
                return str(query[key][0])
        if parsed.path:
            cleaned = re.sub(r"\W+", "_", parsed.path.strip("/"))
            if cleaned:
                return cleaned
    return path.stem


def _normalize_results(results: Iterable[Dict[str, object]]) -> pd.DataFrame:
    """Return a DataFrame with normalized column names from raw result dicts."""

    normalized_rows: List[Dict[str, object]] = []
    for row in results:
        normalized_row: Dict[str, object] = {}
        for key, value in row.items():
            normalized_row[_normalize_column(str(key))] = value
        normalized_rows.append(normalized_row)

    if not normalized_rows:
        return pd.DataFrame()
    return pd.DataFrame(normalized_rows)


# ----------------------------- Core parse logic -----------------------------


def parse_race_file(path: Path) -> pd.DataFrame:
    """Parse a single raw race JSON file into a tidy DataFrame."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    race_id = _extract_race_id(path, payload)

    metadata = payload.get("metadata") or {}
    results = payload.get("results") or []

    df = _normalize_results(results)
    if df.empty:
        logger.warning("No results found in %s", path)
        df = pd.DataFrame()

    # Ensure expected columns exist
    for col in ("rank", "athlete", "nation", "time", "diff"):
        if col not in df.columns:
            df[col] = pd.NA

    # Attach metadata to every row
    meta_prefixed = {f"race_{_normalize_column(k)}": v for k, v in metadata.items()}
    df.insert(0, "race_id", race_id)
    for key, value in meta_prefixed.items():
        df.insert(len(df.columns), key, value)
    df.insert(1, "race_url", payload.get("url"))

    return df


def parse_directory(input_dir: Path, output_dir: Path, *, fmt: str = "parquet", overwrite: bool = False) -> List[Path]:
    """Parse all JSON files under ``input_dir`` and write tidy outputs."""

    input_dir = input_dir.expanduser()
    output_dir = output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        logger.warning("No JSON files found under %s", input_dir)
        return []

    written: List[Path] = []
    for path in json_files:
        df = parse_race_file(path)
        if df.empty:
            continue

        race_id = df["race_id"].iloc[0]
        output_path = output_dir / f"{race_id}.{ 'parquet' if fmt == 'parquet' else 'csv' }"

        if output_path.exists() and not overwrite:
            logger.info("Skipping existing %s", output_path)
            written.append(output_path)
            continue

        if fmt == "parquet":
            df.to_parquet(output_path, index=False)
        elif fmt == "csv":
            df.to_csv(output_path, index=False)
        else:  # pragma: no cover - defensive check
            raise ValueError(f"Unsupported format: {fmt}")

        logger.info("Wrote %s", output_path)
        written.append(output_path)

    return written


# --------------------------------- CLI entry ---------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse FirstSkiSport raw race JSON into tidy tables")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data_raw/firstskisport"),
        help="Directory containing raw *.json files from the scraper",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data_clean/firstskisport"),
        help="Directory to write parsed outputs",
    )
    parser.add_argument(
        "--format",
        choices=["parquet", "csv"],
        default="parquet",
        help="Output format",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing parsed outputs",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parse_directory(args.input_dir, args.output_dir, fmt=args.format, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
