"""
Downloads the district-wise, season-wise crop production series from
data.gov.in (Ministry of Agriculture and Farmers Welfare, resource
35be999b-0208-4354-b557-f6ca9a5355de) and derives per-district yield.

Why this dataset matters: it is the DISTRICT-level label tier the project's
central experiment needs (evaluation/label_granularity/). The existing labels
are national and state annual averages, which RESULTS.md section 5 identifies
as what breaks the models - a vigorous canopy implies a high yield for that
field, but the label it is trained against is a regional mean.

Known constraint, and it drives an architecture decision: **this series ends
in 2015** (verified - zero rows for crop_year >= 2016). Sentinel-2 surface
reflectance only begins in 2017, so these labels CANNOT be matched to the
project's current imagery source. Landsat 5/7/8 do cover 1997-2015, which is
why ingestion/satellite_fetch.py needs a Landsat path before this tier is
usable end to end.

Yield is derived as Production / Area. The source's units are documented as
Area in hectares and Production in tonnes, so the quotient is t/ha - the same
unit as every other label in this project. Rows with Area <= 0 or a missing
Production are dropped rather than imputed.

Run:
    python -m ingestion.datagovin_fetch --crop Rice
"""

import argparse
import csv
import time
from pathlib import Path

import requests

from ingestion.config import RAW_DIR

OUT_DIR = RAW_DIR / "external" / "datagovin"
KEY_PATH = OUT_DIR / "api_key.txt"
RESOURCE_ID = "35be999b-0208-4354-b557-f6ca9a5355de"
BASE = f"https://api.data.gov.in/resource/{RESOURCE_ID}"


def fetch_crop(crop: str, page_size: int = 1000, pause_s: float = 1.5) -> list[dict]:
    key = KEY_PATH.read_text().strip()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    rows, offset = [], 0
    while True:
        for attempt in range(3):
            try:
                resp = session.get(
                    BASE,
                    params={
                        "api-key": key,
                        "format": "json",
                        "limit": page_size,
                        "offset": offset,
                        "filters[crop]": crop,
                    },
                    timeout=180,
                )
                break
            except requests.RequestException as e:
                print(f"  offset {offset} attempt {attempt}: {type(e).__name__}")
                time.sleep(5)
        else:
            print(f"  giving up at offset {offset}")
            break

        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code} at offset {offset}")
            break
        recs = resp.json().get("records", [])
        if not recs:
            break
        rows.extend(recs)
        offset += page_size
        print(f"  {crop}: {len(rows)} rows")
        time.sleep(pause_s)
    return rows


def to_yield_rows(records: list[dict]) -> list[dict]:
    """Production / Area -> t/ha. Drops rows that cannot yield a real number
    rather than filling them in."""
    out = []
    for r in records:
        try:
            area = float(r.get("area_") or 0)
            prod = float(r.get("production_") or 0)
        except (TypeError, ValueError):
            continue
        if area <= 0 or prod <= 0:
            continue
        out.append(
            {
                "state": (r.get("state_name") or "").strip(),
                "district": (r.get("district_name") or "").strip(),
                "year": r.get("crop_year"),
                "season": (r.get("season") or "").strip(),
                "crop": (r.get("crop") or "").strip(),
                "area_ha": area,
                "production_t": prod,
                "yield_t_ha": round(prod / area, 4),
            }
        )
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crop", default="Rice")
    args = parser.parse_args()

    print(f"fetching {args.crop} ...")
    records = fetch_crop(args.crop)
    rows = to_yield_rows(records)

    out_path = OUT_DIR / f"district_yield_{args.crop.lower()}.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["state"])
        w.writeheader()
        w.writerows(rows)

    years = sorted({r["year"] for r in rows})
    print(
        f"\n{len(records)} raw rows -> {len(rows)} usable yield rows\n"
        f"districts: {len({(r['state'], r['district']) for r in rows})}\n"
        f"years: {min(years)}-{max(years)}\n"
        f"yield range: {min(r['yield_t_ha'] for r in rows):.2f}-{max(r['yield_t_ha'] for r in rows):.2f} t/ha\n"
        f"wrote -> {out_path}"
    )


if __name__ == "__main__":
    main()
