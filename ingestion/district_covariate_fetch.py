"""
Experiment 4, Phase B - district-level agricultural covariates.

WHAT THIS COLLECTS AND WHY IT IS DEFENSIBLE
-------------------------------------------
Experiment 3 established that Tamil Nadu out-yields Andhra Pradesh and
Telangana by ~0.83 t/ha under matched year, season and Landsat era, and that
the 12 environmental features do not account for it. Phase B looks for real
district-level agricultural covariates that might.

The source used here is the SAME official resource that supplies the yield
labels themselves - data.gov.in resource 35be999b (GoI Ministry of Agriculture
and Farmers Welfare), which reports Area and Production for EVERY crop, not
just Rice. Earlier work fetched it with `filters[crop]=Rice` and therefore only
ever saw the rice rows. Fetching the same resource per state without that
filter yields the full crop portfolio of each district-year, from which
genuinely district-level agricultural-intensity covariates can be derived.

Why this source rather than a new one: it is already verified (publisher,
official status, units - see the AP validation report), it is district-level
by construction, and it is temporally matched to the yield labels year for
year. A separately-published irrigation series would have to be matched across
a different district vintage and a different year convention, introducing new
error into exactly the comparison being made.

THE LEAKAGE HAZARD, STATED UP FRONT
-----------------------------------
The target is rice yield = rice production / rice AREA. Any covariate built
from rice area therefore shares a term with the target's denominator. Two
covariates below are affected and are flagged in DERIVED_COVARIATES with
`yield_denominator_overlap=True`:

    rice_area_share        rice area / gross cropped area
    gross_cropped_area_ha  includes rice area in its sum

They are computed because they are agronomically the most interesting, but the
leakage audit treats them as ineligible for any prediction model, and the
explanatory analysis reports them separately from the clean covariates. The
covariates WITHOUT that overlap are:

    non_rice_cropped_area_ha   sum of area over every crop except Rice
    n_crops_grown              distinct crops reported in the district-year
    n_rice_seasons             distinct seasons rice is reported in - a real
                               cropping-intensity signal (a district growing
                               rice in both Kharif and Rabi is double-cropping)

None of these is a yield, a production figure, or derived from one.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESOURCE_ID = "35be999b-0208-4354-b557-f6ca9a5355de"
BASE = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
OUT_DIR = ROOT / "data" / "raw" / "external" / "district_covariates"
KEY_PATH = ROOT / "data" / "raw" / "external" / "datagovin" / "api_key.txt"

STATES = ["Andhra Pradesh", "Telangana", "Tamil Nadu"]

SOURCE_NAME = (
    "District-wise, season-wise crop production statistics - Government of India, "
    "Ministry of Agriculture and Farmers Welfare (via data.gov.in)"
)
SOURCE_URL = f"https://data.gov.in/resource/{RESOURCE_ID}"

# name -> (definition, unit, yield_denominator_overlap)
DERIVED_COVARIATES = {
    "non_rice_cropped_area_ha": (
        "Sum of reported Area across every crop EXCEPT Rice, for that district, "
        "year and season. A measure of the non-rice agricultural footprint.",
        "hectares", False,
    ),
    "n_crops_grown": (
        "Count of distinct crops with positive reported Area in that district, "
        "year and season. A crop-diversity measure.",
        "count", False,
    ),
    "n_rice_seasons": (
        "Count of distinct seasons in which Rice is reported with positive area "
        "for that district and year. A district reporting rice in both Kharif and "
        "Rabi is double-cropping rice; this is a genuine cropping-intensity signal.",
        "count", False,
    ),
    "gross_cropped_area_ha": (
        "Sum of reported Area across ALL crops including Rice, for that district, "
        "year and season.",
        "hectares", True,
    ),
    "rice_area_share": (
        "Rice area divided by gross cropped area for that district, year and season.",
        "fraction", True,
    ),
}


def fetch_state(state: str, page_size: int = 1000, pause_s: float = 1.0) -> list[dict]:
    key = KEY_PATH.read_text().strip()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows, offset = [], 0
    while True:
        for attempt in range(3):
            try:
                resp = session.get(BASE, params={
                    "api-key": key, "format": "json", "limit": page_size,
                    "offset": offset, "filters[state_name]": state,
                }, timeout=180)
                break
            except requests.RequestException as e:
                print(f"    offset {offset} attempt {attempt}: {type(e).__name__}", flush=True)
                time.sleep(5)
        else:
            print(f"    giving up at offset {offset}", flush=True)
            break
        if resp.status_code != 200:
            print(f"    HTTP {resp.status_code} at offset {offset}", flush=True)
            break
        recs = resp.json().get("records", [])
        if not recs:
            break
        rows.extend(recs)
        offset += page_size
        print(f"    {state}: {len(rows)} rows", flush=True)
        time.sleep(pause_s)
    return rows


def normalise(records: list[dict]) -> pd.DataFrame:
    out = []
    for r in records:
        try:
            area = float(r.get("area_") or 0)
        except (TypeError, ValueError):
            continue
        if area <= 0:
            continue
        out.append({
            "state": (r.get("state_name") or "").strip(),
            "district": (r.get("district_name") or "").strip(),
            "year": r.get("crop_year"),
            "season": (r.get("season") or "").strip(),
            "crop": (r.get("crop") or "").strip(),
            "area_ha": area,
        })
    return pd.DataFrame(out)


def derive(df: pd.DataFrame) -> pd.DataFrame:
    """District x year x season covariates, plus the district-year cropping
    intensity signal. Nothing is imputed; a district-season simply absent from
    the source produces no row."""
    df = df.copy()
    df["year"] = df["year"].astype(int)
    is_rice = df["crop"].str.strip().str.lower() == "rice"

    grp = ["state", "district", "year", "season"]
    gross = df.groupby(grp)["area_ha"].sum().rename("gross_cropped_area_ha")
    ncrops = df.groupby(grp)["crop"].nunique().rename("n_crops_grown")
    nonrice = df[~is_rice].groupby(grp)["area_ha"].sum().rename("non_rice_cropped_area_ha")
    rice = df[is_rice].groupby(grp)["area_ha"].sum().rename("rice_area_ha")

    cov = pd.concat([gross, ncrops, nonrice, rice], axis=1).reset_index()
    cov["non_rice_cropped_area_ha"] = cov["non_rice_cropped_area_ha"].fillna(0.0)
    cov["rice_area_share"] = cov["rice_area_ha"] / cov["gross_cropped_area_ha"]

    # Cropping intensity: how many seasons this district grew rice in this year.
    seasons = (df[is_rice].groupby(["state", "district", "year"])["season"]
               .nunique().rename("n_rice_seasons").reset_index())
    cov = cov.merge(seasons, on=["state", "district", "year"], how="left")
    cov["n_rice_seasons"] = cov["n_rice_seasons"].fillna(0).astype(int)

    cov["source_name"] = SOURCE_NAME
    cov["source_url"] = SOURCE_URL
    cov["retrieved_date"] = date.today().isoformat()
    cov["geographic_level"] = "district"
    return cov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", default=",".join(STATES))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    states = [s.strip() for s in args.states.split(",") if s.strip()]
    raw_frames, fetch_log = [], {}
    for s in states:
        print(f"fetching {s} ...", flush=True)
        recs = fetch_state(s)
        df = normalise(recs)
        fetch_log[s] = {"raw_records": len(recs), "usable_rows": int(len(df))}
        raw_frames.append(df)

    raw = pd.concat(raw_frames, ignore_index=True)
    raw.to_csv(OUT_DIR / "raw_all_crops_three_states.csv", index=False)

    cov = derive(raw)
    cov.to_csv(OUT_DIR / "district_agricultural_covariates.csv", index=False)

    meta = {
        "resource_id": RESOURCE_ID, "source_name": SOURCE_NAME, "source_url": SOURCE_URL,
        "retrieved_date": date.today().isoformat(),
        "geographic_level": "district",
        "states": states,
        "fetch_log": fetch_log,
        "covariate_definitions": {
            k: {"definition": v[0], "unit": v[1], "yield_denominator_overlap": v[2]}
            for k, v in DERIVED_COVARIATES.items()
        },
        "note": (
            "Area units are hectares on the same evidence documented for this resource in "
            "data/raw/external/official_yield/andhra_pradesh/validation_report.md section 5. "
            "No state-level value is ever used as a district-level value: every row here is "
            "aggregated from district rows of the same resource."
        ),
    }
    (OUT_DIR / "covariate_source_metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8")

    print(f"\nraw rows: {len(raw)}   covariate rows: {len(cov)}")
    print(f"districts: {cov.groupby('state')['district'].nunique().to_dict()}")
    print(f"years: {cov['year'].min()}-{cov['year'].max()}")
    print(f"wrote -> {OUT_DIR}")


if __name__ == "__main__":
    main()
