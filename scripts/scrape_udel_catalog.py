#!/usr/bin/env python
"""
Scrape University of Delaware course data into data/raw/courses_raw.json.

UD catalog-specific strategy:
1) Discover the active "Courses" index URL from catalog homepage.
2) Walk paginated course index pages.
3) Collect preview links (preview_course_nopop.php) and filter by department code.
4) Fetch each preview page and store raw text fields.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

DEFAULT_BASE_URL = "https://catalog.udel.edu/"
DEFAULT_DEPARTMENTS = [
    "CISC",
    "DATA",
    "MATH",
    "STAT",
    "MISY",
    "BINF",
    "ACCT",
    "FINC",
    "BUAD",
    "ECON",
    "CHEM",
    "BISC",
]
COURSE_LINK_TEXT_RE = re.compile(r"^([A-Z]{2,5})\s+(\d{3}[A-Z]?)\s*[\u00A0\-–]\s*(.+)$")
PREREQ_RE = re.compile(r"Prereq(?:uisites?)?[:\.]\s*(.+?)(?:\.|$)", re.IGNORECASE)


@dataclass
class RawCourse:
    source_url: str
    department_hint: str
    raw_header: str
    raw_body: str
    raw_prerequisites: str


class UDCatalogScraper:
    def __init__(
        self,
        base_url: str,
        timeout: int,
        min_delay: float,
        max_delay: float,
        retries: int,
        backoff_seconds: float,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            }
        )

    def _get(self, url: str) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep((attempt + 1) * self.backoff_seconds)
                    continue
                resp.raise_for_status()
                time.sleep(random.uniform(self.min_delay, self.max_delay))
                return resp
            except Exception as exc:
                last_exc = exc
                time.sleep((attempt + 1) * self.backoff_seconds)
        raise RuntimeError(f"Failed to fetch {url}: {last_exc}")

    def discover_courses_index_url(self) -> str:
        home = self._get(self.base_url)
        soup = BeautifulSoup(home.text, "html.parser")
        for a in soup.select("a[href]"):
            text = a.get_text(" ", strip=True).lower()
            href = a.get("href", "")
            if text == "courses" and "content.php" in href and "catoid=" in href:
                return urljoin(self.base_url, href)
        raise RuntimeError("Could not find Courses index URL on UD catalog homepage")

    def collect_preview_links(self, courses_index_url: str, max_pages: int) -> list[tuple[str, str, str]]:
        """Return list of tuples (dept_code, link_text, preview_url)."""
        results: list[tuple[str, str, str]] = []
        seen_urls: set[str] = set()

        for cpage in range(1, max_pages + 1):
            page_url = (
                courses_index_url
                if cpage == 1
                else f"{courses_index_url}&filter%5Bcpage%5D={cpage}#acalog_template_course_filter"
            )
            try:
                resp = self._get(page_url)
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            anchors = soup.select("a[href]")
            page_new = 0
            for a in anchors:
                href = a.get("href", "")
                if "preview_course_nopop.php" not in href:
                    continue
                full = urljoin(self.base_url, href)
                if full in seen_urls:
                    continue
                seen_urls.add(full)
                text = a.get_text(" ", strip=True)
                m = COURSE_LINK_TEXT_RE.match(text)
                if not m:
                    # fallback: derive department from link text prefix
                    prefix = text.split(" ", 1)[0].strip().upper()
                    if not re.match(r"^[A-Z]{2,5}$", prefix):
                        continue
                    dept = prefix
                else:
                    dept = m.group(1).upper()
                results.append((dept, text, full))
                page_new += 1

            if page_new == 0 and cpage > 3:
                break

        return results

    def parse_preview_course(self, dept: str, link_text: str, preview_url: str) -> RawCourse | None:
        try:
            resp = self._get(preview_url)
        except Exception:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("#course_preview_title")
        body_el = soup.select_one("td.block_content")

        raw_header = title_el.get_text(" ", strip=True) if title_el else link_text
        raw_body = body_el.get_text(" ", strip=True) if body_el else ""
        if not raw_body:
            return None

        prereq_match = PREREQ_RE.search(raw_body)
        raw_prereq = prereq_match.group(0) if prereq_match else ""

        return RawCourse(
            source_url=preview_url,
            department_hint=dept,
            raw_header=raw_header[:300],
            raw_body=raw_body[:5000],
            raw_prerequisites=raw_prereq[:500],
        )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape UD catalog course data.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--departments", nargs="+", default=DEFAULT_DEPARTMENTS)
    parser.add_argument("--max-index-pages", type=int, default=30)
    parser.add_argument("--max-courses-per-dept", type=int, default=120)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--min-delay", type=float, default=0.2)
    parser.add_argument("--max-delay", type=float, default=0.5)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--backoff-seconds", type=float, default=0.4)
    parser.add_argument("--out", default="data/raw/courses_raw.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    departments = [d.upper() for d in args.departments]

    scraper = UDCatalogScraper(
        base_url=args.base_url,
        timeout=args.timeout,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
    )

    courses_index_url = scraper.discover_courses_index_url()
    links = scraper.collect_preview_links(courses_index_url, max_pages=args.max_index_pages)

    by_dept: dict[str, list[tuple[str, str]]] = {d: [] for d in departments}
    for dept, text, url in links:
        if dept in by_dept:
            by_dept[dept].append((text, url))

    raw_courses: list[RawCourse] = []
    stats = {}
    for dept in departments:
        selected = by_dept.get(dept, [])[: args.max_courses_per_dept]
        stats[dept] = {"discovered": len(by_dept.get(dept, [])), "scraped": 0}
        for text, url in selected:
            item = scraper.parse_preview_course(dept, text, url)
            if item is None:
                continue
            raw_courses.append(item)
            stats[dept]["scraped"] += 1

    payload = {
        "meta": {
            "base_url": args.base_url,
            "courses_index_url": courses_index_url,
            "departments": departments,
            "total_unique_courses": len(raw_courses),
            "department_stats": stats,
        },
        "courses": [asdict(c) for c in raw_courses],
    }

    out_path = Path(args.out)
    write_json(out_path, payload)
    print(f"Saved {len(raw_courses)} raw courses to {out_path}")


if __name__ == "__main__":
    main()
