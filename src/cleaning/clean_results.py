"""Normalize parsed race tables and resolve basic athlete identity issues."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from src.utils.name_matcher import best_match, canonicalize_name
from src.utils.time_utils import infer_race_date, parse_gap, parse_time_to_seconds

logger = logging.getLogger(__name__)

STATUS_VALUES = {"dns", "dnf", "dsq"}
NATION_FIXES: Dict[str, str] = {
    "rus": "RUS",
    "russia": "RUS",
    "usa": "USA",
    "us": "USA",
    "gbr": "GBR",
    "uk": "GBR",
    "swe": "SWE",
    "nor": "NOR",
    "fin": "FIN",
}


def _normalize_nation(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip().upper()
    cleaned = cleaned.replace(".", "")
    return NATION_FIXES.get(cleaned.lower(), cleaned) or None


def _extract_status(rank: Optional[str], time_value: Optional[str]) -> Optional[str]:
    rank_lower = (str(rank).lower() if rank is not None else "").strip()
    time_lower = (str(time_value).lower() if time_value is not None else "").strip()

    for candidate in (rank_lower, time_lower):
        if candidate in STATUS_VALUES:
            return candidate.upper()
    return None


def _clean_athlete(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = " ".join(value.replace("  ", " ").split())
    return normalized.strip() or None


def _resolve_duplicates(names: Iterable[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    canonical_seen: Dict[str, str] = {}

    for name in names:
        if not name:
            continue
        canon = canonicalize_name(name)
        if canon in canonical_seen:
            mapping[name] = canonical_seen[canon]
            continue

        match = best_match(canon, canonical_seen.keys(), threshold=94)
        if match:
            mapping[name] = canonical_seen[match[0]]
            continue

        canonical_seen[canon] = name
        mapping[name] = name

    return mapping


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned result table with parsed times and normalized names."""

    if df.empty:
        return df

    df = df.copy()
    df["athlete"] = df["athlete"].apply(_clean_athlete)
    name_map = _resolve_duplicates(df["athlete"].dropna().tolist())
    df["athlete_canonical"] = df["athlete"].map(name_map)

    df["nation"] = df["nation"].apply(_normalize_nation)

    df["status"] = [
        _extract_status(rank, time_val) for rank, time_val in zip(df.get("rank"), df.get("time"))
    ]

    df["time_seconds"] = df.get("time").apply(parse_time_to_seconds)
    df["diff_seconds"] = df.get("diff").apply(parse_gap)

    if "race_date" in df.columns:
        df["race_date_parsed"] = df["race_date"].apply(infer_race_date)
    else:
        df["race_date_parsed"] = None

    for col in ("rank", "bib", "start"):
        if col in df.columns:
            df[col] = df[col].apply(lambda x: int(x) if pd.notna(x) and str(x).isdigit() else x)

    expected_order = [
        "race_id",
        "race_url",
        "race_title",
        "race_date",
        "race_date_parsed",
        "race_location",
        "race_category",
        "race_discipline",
        "race_sex",
        "athlete",
        "athlete_canonical",
        "nation",
        "bib",
        "rank",
        "status",
        "time",
        "time_seconds",
        "diff",
        "diff_seconds",
        "start",
        "club",
        "fis_code",
    ]

    # Preserve any additional columns from the parser while ordering key fields first
    remaining = [c for c in df.columns if c not in expected_order]
    ordered_columns = [c for c in expected_order if c in df.columns] + remaining
    return df[ordered_columns]


def clean_directory(
    input_dir: Path,
    output_dir: Path,
    *,
    fmt: str = "parquet",
    overwrite: bool = False,
) -> List[Path]:
    input_dir = input_dir.expanduser()
    output_dir = output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(list(input_dir.glob("*.parquet")) + list(input_dir.glob("*.csv")))
    if not files:
        logger.warning("No parsed race files found in %s", input_dir)
        return []

    written: List[Path] = []
    for path in files:
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)

        cleaned = clean_dataframe(df)
        if cleaned.empty:
            continue

        race_id = str(cleaned["race_id"].iloc[0]) if "race_id" in cleaned.columns else path.stem
        output_path = output_dir / f"{race_id}.{ 'parquet' if fmt == 'parquet' else 'csv' }"

        if output_path.exists() and not overwrite:
            logger.info("Skipping existing %s", output_path)
            written.append(output_path)
            continue

        if fmt == "parquet":
            cleaned.to_parquet(output_path, index=False)
        elif fmt == "csv":
            cleaned.to_csv(output_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        logger.info("Wrote %s", output_path)
        written.append(output_path)

    return written


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean parsed FirstSkiSport race tables")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data_clean/firstskisport"),
        help="Directory containing parsed parquet/csv race tables",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data_clean/firstskisport_clean"),
        help="Destination for cleaned outputs",
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
        help="Overwrite existing cleaned outputs",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    clean_directory(args.input_dir, args.output_dir, fmt=args.format, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
