"""Create train/validation/test splits from the master table."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _load_master(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _assign_split(df: pd.DataFrame, val_year: int, test_year: int) -> pd.DataFrame:
    if df.empty:
        return df

    work = df.copy()
    if "race_date_parsed" in work.columns:
        work["race_year"] = work["race_date_parsed"].apply(lambda d: d.year if not pd.isna(d) else None)
    elif "race_date" in work.columns:
        work["race_year"] = work["race_date"].str.extract(r"(\d{4})").astype(float)
    else:
        work["race_year"] = None

    def label(year: Optional[float]) -> str:
        if year is None or pd.isna(year):
            return "train"
        if year >= test_year:
            return "test"
        if year >= val_year:
            return "val"
        return "train"

    work["split"] = work["race_year"].apply(label)
    return work


def write_splits(df: pd.DataFrame, output_dir: Path, *, fmt: str = "parquet", overwrite: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for split in ["train", "val", "test"]:
        subset = df[df["split"] == split]
        output_path = output_dir / f"{split}.{ 'parquet' if fmt == 'parquet' else 'csv' }"
        if output_path.exists() and not overwrite:
            logger.info("Skipping existing %s", output_path)
            continue
        if fmt == "parquet":
            subset.to_parquet(output_path, index=False)
        elif fmt == "csv":
            subset.to_csv(output_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {fmt}")
        logger.info("Wrote %s split to %s", split, output_path)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Split master table into train/val/test by season")
    parser.add_argument(
        "--master",
        type=Path,
        default=Path("data_clean/master/master.parquet"),
        help="Path to the master dataset",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data_clean/splits"),
        help="Destination directory for splits",
    )
    parser.add_argument(
        "--val-year",
        type=int,
        default=2022,
        help="First season assigned to validation",
    )
    parser.add_argument(
        "--test-year",
        type=int,
        default=2023,
        help="First season assigned to test",
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
        help="Overwrite existing splits",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    master = _load_master(args.master)
    if master.empty:
        logger.warning("Master dataset is empty; nothing to split")
        return

    assigned = _assign_split(master, args.val_year, args.test_year)
    write_splits(assigned, args.output_dir, fmt=args.format, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
