#!/usr/bin/env python
"""
Fetch specific missing course IDs directly from UD catalog preview pages.

Inputs:
- data/processed/missing_prereqs_report.json (or explicit --course-ids)

Output:
- data/raw/courses_raw_missing_targets.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://catalog.udel.edu/"
UG_INDEX = "https://catalog.udel.edu/content.php?catoid=94&navoid=34643"
GR_INDEX = "https://catalog.udel.edu/content.php?catoid=93&navoid=30539"
LINK_RE = re.compile(r"^([A-Z]{2,5})\s+(\d{3}[A-Z]?)\b")
PREREQ_RE = re.compile(r"Prereq(?:uisites?)?[:\.]\s*(.+?)(?:\s[A-Z][A-Z ]{3,}[:\.]|$)", re.IGNORECASE)


@dataclass
class RawCourse:
    source_url: str
    department_hint: str
    raw_header: str
    raw_body: str
    raw_prerequisites: str


class Client:
    def __init__(self, timeout: int = 12, retries: int = 2):
        self.timeout = timeout
        self.retries = retries
        self.s = requests.Session()
        self.s.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            }
        )

    def get(self, url: str) -> requests.Response:
        last = None
        for i in range(self.retries):
            try:
                r = self.s.get(url, timeout=self.timeout)
                r.raise_for_status()
                time.sleep(random.uniform(0.0, 0.08))
                return r
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep((i + 1) * 0.2)
        raise RuntimeError(f"GET failed for {url}: {last}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch missing prerequisite course pages.")
    p.add_argument("--missing-report", default="data/processed/missing_prereqs_report.json")
    p.add_argument("--course-ids", nargs="*", default=None)
    p.add_argument("--max-pages", type=int, default=90)
    p.add_argument("--out", default="data/raw/courses_raw_missing_targets.json")
    return p.parse_args()


def load_target_ids(args: argparse.Namespace) -> set[str]:
    if args.course_ids:
        return {x.strip().upper() for x in args.course_ids if x.strip()}
    report = json.loads(Path(args.missing_report).read_text(encoding="utf-8"))
    ids = {row["missing_course_id"].upper() for row in report.get("top_missing_prereqs", [])}
    return ids


def index_pages(index_url: str, max_pages: int) -> list[str]:
    pages = [index_url]
    for i in range(2, max_pages + 1):
        pages.append(f"{index_url}&filter%5Bcpage%5D={i}#acalog_template_course_filter")
    return pages


def collect_preview_links(
    client: Client,
    targets: set[str],
    max_pages: int,
) -> dict[str, str]:
    found: dict[str, str] = {}
    for index_url in [UG_INDEX, GR_INDEX]:
        for page_url in index_pages(index_url, max_pages):
            try:
                r = client.get(page_url)
            except Exception:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if "preview_course_nopop.php" not in href:
                    continue
                text = a.get_text(" ", strip=True)
                m = LINK_RE.match(text)
                if not m:
                    continue
                cid = f"{m.group(1)}-{m.group(2)}".upper()
                if cid in targets and cid not in found:
                    found[cid] = urljoin(BASE, href)
            if len(found) == len(targets):
                return found
    return found


def parse_preview(client: Client, cid: str, preview_url: str) -> RawCourse | None:
    try:
        r = client.get(preview_url)
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    title_el = soup.select_one("#course_preview_title")
    body_el = soup.select_one("td.block_content")
    raw_header = title_el.get_text(" ", strip=True) if title_el else cid
    raw_body = body_el.get_text(" ", strip=True) if body_el else ""
    if not raw_body:
        return None
    m = PREREQ_RE.search(raw_body)
    prereq = m.group(0) if m else ""
    return RawCourse(
        source_url=preview_url,
        department_hint=cid.split("-")[0],
        raw_header=raw_header[:300],
        raw_body=raw_body[:5000],
        raw_prerequisites=prereq[:500],
    )


def main() -> None:
    args = parse_args()
    targets = load_target_ids(args)
    client = Client()

    found_links = collect_preview_links(client, targets, args.max_pages)
    raw_courses: list[dict] = []
    missing_not_found = sorted(targets - set(found_links.keys()))

    for cid in sorted(found_links):
        item = parse_preview(client, cid, found_links[cid])
        if item is not None:
            raw_courses.append(asdict(item))

    out = {
        "meta": {
            "targets_requested": sorted(targets),
            "targets_found": sorted(found_links.keys()),
            "targets_not_found": missing_not_found,
            "total_fetched": len(raw_courses),
        },
        "courses": raw_courses,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"Saved {len(raw_courses)} targeted raw courses to {out_path}")
    print(f"Found {len(found_links)}/{len(targets)} targets")
    if missing_not_found:
        print("Not found:", ", ".join(missing_not_found[:20]))


if __name__ == "__main__":
    main()
