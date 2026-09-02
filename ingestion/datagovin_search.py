"""
Scans data.gov.in's Agriculture sector for district-level crop yield resources.

The portal's /lists endpoint ignores full-text `q`, and `filters[title]` only
does exact-ish matching, so the practical route is to page the whole
Agriculture sector (~19.5k resources) and filter titles locally.

What we need, and why each condition matters for this project:
  - "district" in the title: the entire point is a label finer than the
    state-level figures currently in data/raw/yield_labels/ (see RESULTS.md
    section 5 - label granularity is what breaks the models).
  - yield / production / area: production + area is enough, yield is derivable.
  - a year >= 2017: Sentinel-2 surface reflectance starts in 2017, so a
    dataset ending in 2015 cannot be matched to any imagery we can pull.

Run:
    python -m ingestion.datagovin_search
"""

import json
import re
from pathlib import Path

import requests

from ingestion.config import RAW_DIR

OUT_DIR = RAW_DIR / "external" / "datagovin"
KEY_PATH = OUT_DIR / "api_key.txt"
LISTS_URL = "https://api.data.gov.in/lists"

CROP_WORDS = ("yield", "production", "area under", "principal crop", "crop")
YEAR_RE = re.compile(r"(20[0-3]\d)")
MIN_YEAR = 2017


def _score(title: str) -> tuple[bool, int]:
    """Returns (is_candidate, best_year_found). A title with no year is kept
    if it otherwise matches - many series titles omit the year and carry it in
    the data instead."""
    t = title.lower()
    if "district" not in t:
        return False, 0
    if not any(w in t for w in CROP_WORDS):
        return False, 0
    years = [int(y) for y in YEAR_RE.findall(title)]
    best = max(years) if years else 0
    if years and best < MIN_YEAR:
        return False, best
    return True, best


def main(page_size: int = 100, max_pages: int = 250):
    key = KEY_PATH.read_text().strip()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    hits, scanned, offset = [], 0, 0
    for page in range(max_pages):
        try:
            resp = session.get(
                LISTS_URL,
                params={
                    "api-key": key,
                    "format": "json",
                    "filters[sector]": "Agriculture",
                    "limit": page_size,
                    "offset": offset,
                },
                timeout=120,
            )
        except requests.RequestException as e:
            print(f"page {page} offset {offset}: {type(e).__name__} - retrying once")
            continue
        if resp.status_code != 200:
            print(f"page {page}: HTTP {resp.status_code}")
            break

        records = resp.json().get("records", [])
        if not records:
            break
        scanned += len(records)
        for rec in records:
            title = rec.get("title", "") or ""
            ok, year = _score(title)
            if ok:
                hits.append(
                    {
                        "title": title,
                        "resource_id": rec.get("index_name"),
                        "best_year_in_title": year,
                        "org": rec.get("org"),
                        "desc": (rec.get("desc") or "")[:300],
                    }
                )
        offset += page_size
        if page % 10 == 0:
            print(f"scanned {scanned}  candidates {len(hits)}")

    hits.sort(key=lambda h: -h["best_year_in_title"])
    out = OUT_DIR / "district_yield_candidates.json"
    out.write_text(json.dumps({"scanned": scanned, "candidates": hits}, indent=2))
    print(f"\nscanned {scanned} Agriculture resources, {len(hits)} candidates")
    for h in hits[:40]:
        print(f"  [{h['best_year_in_title'] or '----'}] {h['title'][:100]}")
    print(f"\nwrote -> {out}")


if __name__ == "__main__":
    main()
