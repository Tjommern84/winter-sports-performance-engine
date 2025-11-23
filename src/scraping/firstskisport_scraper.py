"""Scraper for FirstSkiSport race result pages.

The module focuses on downloading and lightly parsing race result pages from
FirstSkiSport so they can be stored under ``data_raw`` for later parsing and
cleaning.

The scraper is intentionally conservative: it respects caching, offers optional
throttling, and saves both the raw HTML and a normalized CSV of the primary
results table when present.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

import requests
import requests_cache
from bs4 import BeautifulSoup

DEFAULT_BASE_TEMPLATE = "https://firstskisport.com/xcski/race.php?raceid={race_id}"

logger = logging.getLogger(__name__)


@dataclass
class RaceMetadata:
    """High-level details parsed from a race page."""

    title: Optional[str] = None
    date: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    discipline: Optional[str] = None
    sex: Optional[str] = None


@dataclass
class AthleteResult:
    """A single athlete's result row."""

    rank: Optional[str] = None
    bib: Optional[str] = None
    athlete: Optional[str] = None
    nation: Optional[str] = None
    time: Optional[str] = None
    diff: Optional[str] = None
    club: Optional[str] = None
    start: Optional[str] = None
    fis_code: Optional[str] = None


# ----------------------------- Session helpers ------------------------------


def build_session(cache_path: Path | str = ".firstskisport_cache",
                  expire_after: Optional[timedelta] = timedelta(hours=6)) -> requests.Session:
    """Return a cached requests session with sane defaults."""

    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    session = requests_cache.CachedSession(
        cache_name=str(cache_path),
        expire_after=expire_after,
        allowable_methods=("GET", "HEAD"),
        stale_if_error=True,
    )
    session.headers.update(
        {
            "User-Agent": (
                "winter-sports-performance-engine scraper (+https://github.com/)"  # noqa: E501
            )
        }
    )
    return session


# ------------------------------- Parsing logic ------------------------------


def _normalize_header(header: str) -> str:
    header = header.strip().lower()
    header = re.sub(r"\s+", " ", header)
    return header


def parse_metadata(soup: BeautifulSoup) -> RaceMetadata:
    """Extract basic race metadata using common FirstSkiSport patterns."""

    title = None
    header = soup.find(["h1", "h2"])
    if header:
        title = header.get_text(strip=True)

    # Many FirstSkiSport pages have a block of descriptive <p> tags near the top
    # containing date and venue information. Grab the first few lines if present.
    info_block = soup.find("div", class_=re.compile("event-info|race-info"))
    info_text: List[str] = []
    if info_block:
        for child in info_block.stripped_strings:
            info_text.append(child)
    else:
        paragraphs = soup.find_all("p", limit=3)
        for p_tag in paragraphs:
            info_text.extend(list(p_tag.stripped_strings))

    date, location = None, None
    for text in info_text:
        if re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}", text):
            date = text
        if any(keyword in text.lower() for keyword in ["venue", "location", "place"]):
            location = text.split(":")[-1].strip()

    # Discipline/sex/category are heuristically pulled from keywords in the title.
    discipline, sex, category = None, None, None
    if title:
        lowered = title.lower()
        if "sprint" in lowered:
            discipline = "Sprint"
        elif any(k in lowered for k in ["10 km", "15 km", "20 km", "50 km", "30 km", "relay", "mass start"]):
            discipline = "Distance"
        if "women" in lowered or "ladies" in lowered or "w" in lowered.split():
            sex = "Women"
        if "men" in lowered or "m" in lowered.split():
            sex = "Men"
        if "world cup" in lowered:
            category = "World Cup"
        elif "world championship" in lowered:
            category = "World Championship"
        elif "olympic" in lowered:
            category = "Olympics"

    return RaceMetadata(
        title=title,
        date=date,
        location=location,
        category=category,
        discipline=discipline,
        sex=sex,
    )


def parse_results_table(soup: BeautifulSoup) -> List[AthleteResult]:
    """Parse the first tabular results on the page into ``AthleteResult`` rows."""

    tables = soup.find_all("table")
    if not tables:
        return []

    # Choose the table that has the richest set of headers.
    table = max(tables, key=lambda t: len(t.find_all("th")))
    headers = [_normalize_header(h.get_text()) for h in table.find_all("th")]

    header_map: Dict[str, str] = {}
    for idx, header in enumerate(headers):
        if "rank" in header or "pos" in header:
            header_map[idx] = "rank"
        elif header in {"bib", "start no", "start"}:
            header_map[idx] = "bib"
        elif "name" in header or "athlete" in header:
            header_map[idx] = "athlete"
        elif "nation" in header or header == "nat":
            header_map[idx] = "nation"
        elif header.startswith("time") or header == "result":
            header_map[idx] = "time"
        elif "gap" in header or "diff" in header:
            header_map[idx] = "diff"
        elif "club" in header:
            header_map[idx] = "club"
        elif "fis" in header:
            header_map[idx] = "fis_code"
        else:
            header_map[idx] = header

    results: List[AthleteResult] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells or row.find("th"):
            # skip header rows
            continue
        values: Dict[str, Optional[str]] = {}
        for idx, cell in enumerate(cells):
            key = header_map.get(idx)
            if not key:
                continue
            values[key] = cell.get_text(strip=True) if cell else None
        if values:
            results.append(AthleteResult(**values))

    return results


# ------------------------------- Scraper core -------------------------------


def fetch_race_html(session: requests.Session, url: str, delay: float = 0.5) -> str:
    """Download a race page, applying a delay when the request is not cached."""

    response = session.get(url)
    if not getattr(response, "from_cache", False) and delay:
        time.sleep(delay)
    response.raise_for_status()
    return response.text


def scrape_race(session: requests.Session, url: str, delay: float = 0.5) -> Dict[str, object]:
    """Fetch and parse a race page into metadata and result rows."""

    logger.info("Fetching %s", url)
    html = fetch_race_html(session, url, delay=delay)
    soup = BeautifulSoup(html, "lxml")

    metadata = parse_metadata(soup)
    results = parse_results_table(soup)

    return {
        "url": url,
        "metadata": asdict(metadata),
        "results": [asdict(r) for r in results],
        "raw_html": html,
    }


def persist_race(payload: Dict[str, object], output_dir: Path) -> Dict[str, Path]:
    """Write raw HTML, metadata JSON, and result CSV for a scraped race."""

    output_dir.mkdir(parents=True, exist_ok=True)

    parsed_url = urlparse(str(payload.get("url")))
    race_id = None
    for part in parsed_url.query.split("&"):
        if "race" in part and "=" in part:
            race_id = part.split("=")[-1]
            break
        if "id=" in part:
            race_id = part.split("=")[-1]
            break
    if not race_id:
        race_id = re.sub(r"\W+", "_", parsed_url.path.strip("/")) or "race"

    base = output_dir / race_id

    html_path = base.with_suffix(".html")
    html_path.write_text(str(payload.get("raw_html", "")), encoding="utf-8")

    json_path = base.with_suffix(".json")
    with json_path.open("w", encoding="utf-8") as f:
        json.dump({k: v for k, v in payload.items() if k != "raw_html"}, f, indent=2)

    csv_path = base.with_suffix(".csv")
    results: List[Dict[str, Optional[str]]] = payload.get("results", [])  # type: ignore[assignment]
    if results:
        fieldnames: List[str] = sorted({key for row in results for key in row.keys()})
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
    else:
        csv_path.write_text("", encoding="utf-8")

    return {"html": html_path, "json": json_path, "csv": csv_path}


def scrape_and_save(session: requests.Session, url: str, output_dir: Path, delay: float = 0.5) -> Dict[str, Path]:
    payload = scrape_race(session, url, delay=delay)
    return persist_race(payload, output_dir)


# --------------------------------- CLI entry --------------------------------


def _build_urls(race_ids: Iterable[str], base_template: str) -> List[str]:
    return [base_template.format(race_id=race_id) for race_id in race_ids]


def _parse_expiry(hours: float) -> timedelta:
    return timedelta(hours=hours)


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Scrape FirstSkiSport race pages")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--race-id", nargs="+", help="Race ID(s) to scrape")
    group.add_argument("--race-url", nargs="+", help="Full race URL(s) to scrape")
    parser.add_argument(
        "--output-dir", default=Path("data_raw/firstskisport"), type=Path, help="Directory to write raw outputs",
    )
    parser.add_argument(
        "--base-template",
        default=DEFAULT_BASE_TEMPLATE,
        help="Template for constructing race URLs when using --race-id",
    )
    parser.add_argument(
        "--cache-expiry-hours",
        type=float,
        default=6,
        help="Hours to keep cached responses before re-fetching",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay (seconds) between uncached requests",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    session = build_session(expire_after=_parse_expiry(args.cache_expiry_hours))

    urls = args.race_url if args.race_url else _build_urls(args.race_id, args.base_template)

    for url in urls:
        try:
            payload = scrape_race(session, url, delay=args.delay)
            paths = persist_race(payload, args.output_dir)
            logger.info("Saved race to %s", paths)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to scrape %s: %s", url, exc)


if __name__ == "__main__":
    main()
