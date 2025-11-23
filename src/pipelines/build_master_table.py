"""Combine cleaned results with feature tables into a master dataset."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.features.form import last_finish_position, recent_rank_average
from src.features.rating import update_ratings

logger = logging.getLogger(__name__)


def _load_cleaned(input_dir: Path) -> pd.DataFrame:
    files = sorted(list(input_dir.glob("*.parquet")) + list(input_dir.glob("*.csv")))
    frames: List[pd.DataFrame] = []
    for path in files:
        if path.suffix == ".parquet":
            frames.append(pd.read_parquet(path))
        else:
            frames.append(pd.read_csv(path))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_master(input_dir: Path) -> pd.DataFrame:
    cleaned = _load_cleaned(input_dir)
    if cleaned.empty:
        logger.warning("No cleaned data found under %s", input_dir)
        return cleaned

    form = recent_rank_average(cleaned)
    last_pos = last_finish_position(cleaned)
    ratings = update_ratings(cleaned)

    merged = cleaned.merge(form, on=["race_id", "athlete_canonical"], how="left")
    merged = merged.merge(last_pos, on=["race_id", "athlete_canonical"], how="left")
    merged = merged.merge(ratings, on=["race_id", "athlete_canonical"], how="left")

    return merged


def write_master(df: pd.DataFrame, output_path: Path, *, fmt: str = "parquet", overwrite: bool = False) -> Path:
    output_path = output_path.expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not overwrite:
        logger.info("Skipping existing %s", output_path)
        return output_path

    if fmt == "parquet":
        df.to_parquet(output_path, index=False)
    elif fmt == "csv":
        df.to_csv(output_path, index=False)
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    logger.info("Wrote master table to %s", output_path)
    return output_path


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build master dataset with features")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data_clean/firstskisport_clean"),
        help="Directory with cleaned race tables",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data_clean/master/master.parquet"),
        help="Output file for the combined master table",
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
        help="Overwrite existing master output",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    master = build_master(args.input_dir)
    if master.empty:
        logger.warning("Master table is empty; nothing written")
        return

    write_master(master, args.output, fmt=args.format, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
