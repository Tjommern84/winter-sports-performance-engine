# Winter Sports Performance Engine

A modular pipeline for scraping, cleaning, structuring, and modeling winter sports performance data.
Phase 1 begins with cross-country skiing (XC), later extendable to biathlon, ski jumping, alpine, and Nordic combined.

## Project Structure

src/
scraping/ # Downloading & caching race results
parsing/ # Converting raw HTML/CSV into structured tables
cleaning/ # Standardizing names, nations, times, removing errors
features/ # Form scores, trends, athlete ratings
utils/ # Shared utilities (time parsing, config, matching)
pipelines/ # Scripts to generate master tables and dataset splits
data_raw/ # Raw scraped dumps (kept for reproducibility)
data_clean/ # Cleaned, normalized datasets
models/ # Trained ML models
notebooks/ # Exploratory analysis, validation


## Goals (Phase 1)

1. Automatic scraping of race results
2. Standardized and clean master dataset
3. Athlete identity resolution
4. Form/Trend/Ratings feature library
5. ML-ready training dataset

## Current status
- FirstSkiSport scraper implemented in `src/scraping/firstskisport_scraper.py` with caching, basic metadata parsing, and CSV/JSON/HTML export under `data_raw/firstskisport/`.
- Parser implemented in `src/parsing/parse_race_results.py` to convert raw JSON dumps into tidy tables with race metadata and normalized result columns (writes Parquet/CSV under `data_clean/firstskisport/`).
- Cleaning pipeline in `src/cleaning/clean_results.py` normalizes athlete names, nations, status flags, and parses times into numeric features; writes cleaned Parquet/CSV to `data_clean/firstskisport_clean/`.
- Feature and pipeline utilities implemented (`src/features/*.py`, `src/pipelines/*.py`) for basic form metrics, Elo-style ratings, master table assembly, and dataset splits.
- `requirements.txt` declares dependencies for scraping, data wrangling, ML, and visualization; no virtual environment is committed and data directories are expected to be created locally.

## Recommended next steps
- Enrich cleaning rules (manual override mappings, better nation dictionaries, and date parsing for edge cases) and add unit tests.
- Iterate on feature quality (course/discipline-aware form, split-based speed metrics) and rating stability.
- Harden pipelines with schema validation, progress logging, and CI automation.

## Using the FirstSkiSport scraper

- CLI entry point: `python -m src.scraping.firstskisport_scraper`.
- Typical usage (scrape two races by ID):

  ```bash
  python -m src.scraping.firstskisport_scraper --race-id 41460 41461 --delay 1.5 --cache-expiry-hours 6
  ```

- Outputs (per race) land in `data_raw/firstskisport/` by default with the basename derived from the `raceid`:
  - `*.html` — raw HTML of the page
  - `*.json` — structured dictionary with `metadata` and `results`
  - `*.csv` — flattened table of results with unified headers

- Options:
  - `--race-url` to scrape from explicit URLs instead of IDs
  - `--output-dir` to change destination
  - `--delay` to throttle between requests (seconds)
  - `--cache-expiry-hours` to control how long cached responses are reused

## Parsing scraped races

- CLI entry point: `python -m src.parsing.parse_race_results`.
- Typical usage (convert all JSON dumps to Parquet):

  ```bash
  python -m src.parsing.parse_race_results --input-dir data_raw/firstskisport --output-dir data_clean/firstskisport --format parquet
  ```

- Behavior:
  - Reads every `*.json` file in the input directory and normalizes column names.
  - Inserts race metadata (prefixed with `race_`) on every row and extracts `race_id`/`race_url`.
  - Writes one output file per race in Parquet (default) or CSV, skipping existing outputs unless `--overwrite` is set.

## Cleaning parsed races

- CLI entry point: `python -m src.cleaning.clean_results`.
- Typical usage (clean parsed Parquet to a new folder):

  ```bash
  python -m src.cleaning.clean_results --input-dir data_clean/firstskisport --output-dir data_clean/firstskisport_clean --format parquet
  ```

- Behavior:
  - Standardizes athlete names and nations, derives simple status codes (DNS/DNF/DSQ), and parses times into seconds and gaps into numeric values.
  - Adds `race_date_parsed` when the raw metadata contains a parseable date.
  - Writes one cleaned file per race (Parquet or CSV); skips existing outputs unless `--overwrite` is provided.

## Building master tables and splits

- Build master dataset with features:

  ```bash
  python -m src.pipelines.build_master_table --input-dir data_clean/firstskisport_clean --output data_clean/master/master.parquet
  ```

- Split into train/val/test by season (based on race year):

  ```bash
  python -m src.pipelines.split_data --master data_clean/master/master.parquet --output-dir data_clean/splits --val-year 2022 --test-year 2023
  ```

- Feature set currently includes rolling average rank, last finish position, and a simplified Elo-style rating calculated per race. Outputs are joined onto the cleaned tables in the master dataset.
