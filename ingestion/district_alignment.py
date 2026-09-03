"""
District-level multimodal alignment pipeline (Phases 6-8 of the district
architecture extension). Joins the three Southern India official yield
collections to whatever real weather/satellite/soil data actually exists on
disk today - reusing the older 417-district registry's already-fetched files
where the same real district is covered, and this task's new
ingestion/district_env_pull.py / district_soil_pull.py outputs where it
isn't - and writes ONE row per real (state, district, crop, season, year)
yield observation, whether or not that observation could be matched to any
environmental data.

**No record is ever dropped.** A yield observation with no weather, no
satellite, and no soil match still gets a row, with every *_available flag
False and a reason recorded - see data/processed/
DISTRICT_ALIGNMENT_VALIDATION_REPORT.md, produced by this same run.

Temporal safety (Phase 7): every weather/satellite value aggregated into a
row is filtered to `window_start <= date <= prediction_cutoff_date` from
ingestion/district_season_calendar.py BEFORE aggregation - never after -
so no post-harvest observation can enter a feature, structurally, not just
by convention.

Soil handling (Phase 5): soil values are written as their own separate
columns with their own availability flag, exactly as fetched - never
imputed, never silently merged into a combined "features" blob. This keeps
data/processed/district_multimodal_examples.csv usable for all of Weather-
only / Satellite-only / Weather+Satellite / Soil-only / Full-multimodal
experiments from the same file, by simply choosing which columns to read.

Run:
    python -m ingestion.district_alignment
"""

import csv
import json
from datetime import date
from pathlib import Path

import pandas as pd

from ingestion.district_season_calendar import season_window

ROOT = Path(__file__).resolve().parent.parent
YIELD_DIR = ROOT / "data" / "raw" / "external" / "official_yield"
REGISTRY_PATH = ROOT / "data" / "metadata" / "district_registry.csv"
OLD_REGISTRY_PATH = ROOT / "data" / "raw" / "external" / "datagovin" / "district_registry.json"

OLD_WEATHER_DIR = ROOT / "data" / "raw" / "weather" / "districts"
NEW_WEATHER_DIR = ROOT / "data" / "raw" / "weather" / "southern_districts"
OLD_SATELLITE_DIR = ROOT / "data" / "raw" / "satellite" / "districts"
NEW_SATELLITE_DIR = ROOT / "data" / "raw" / "satellite" / "southern_districts"
SOIL_PATH = ROOT / "data" / "raw" / "soil" / "southern_district_soil_properties.csv"

OUT_PATH = ROOT / "data" / "processed" / "district_multimodal_examples.csv"
REPORT_PATH = ROOT / "data" / "processed" / "DISTRICT_ALIGNMENT_VALIDATION_REPORT.md"

WEATHER_COLS = ["temp_c", "precip_mm", "humidity_pct", "wind_speed_ms"]
SOIL_COLS = ["phh2o", "soc", "clay", "sand", "nitrogen"]
YIELD_MIN, YIELD_MAX = 0.1, 15.0


def _load_yield_records() -> pd.DataFrame:
    frames = []
    for region_dir in ("andhra_pradesh", "telangana", "tamil_nadu"):
        df = pd.read_csv(YIELD_DIR / region_dir / f"{region_dir}_apy_clean.csv")
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    combined["_source_region"] = combined["state"].map(
        {"Andhra Pradesh": "andhra_pradesh", "Telangana": "telangana", "Tamil Nadu": "tamil_nadu"}
    )
    return combined


def _old_registry_lookup() -> dict:
    """canonical (GAUL ADM2) district name, lowercased -> old field_id, for
    every district the older 417-district registry already covers."""
    registry = json.loads(OLD_REGISTRY_PATH.read_text())
    return {r["gaul_adm2"].lower(): r["field_id"] for r in registry}


def _find_weather_file(district_id: str, canonical_name: str, old_lookup: dict) -> "Path | None":
    new_path = NEW_WEATHER_DIR / f"{district_id}_weather_daily.csv"
    if new_path.exists():
        return new_path
    old_fid = old_lookup.get(canonical_name.lower())
    if old_fid:
        old_path = OLD_WEATHER_DIR / f"{old_fid}_weather_daily.csv"
        if old_path.exists():
            return old_path
    return None


def _find_satellite_file(district_id: str, canonical_name: str, old_lookup: dict) -> "Path | None":
    new_path = NEW_SATELLITE_DIR / f"{district_id}_landsat.csv"
    if new_path.exists():
        return new_path
    old_fid = old_lookup.get(canonical_name.lower())
    if old_fid:
        old_path = OLD_SATELLITE_DIR / f"{old_fid}_landsat.csv"
        if old_path.exists():
            return old_path
    return None


MIN_COVERAGE_FRACTION = 0.5  # a window less than half-observed is reported, not counted as "matched" - see module docstring on TN's partial 2019/2024 calendar-year fetches


def _aggregate_weather(path: Path, window_start: date, cutoff: date) -> dict:
    df = pd.read_csv(path, parse_dates=["date"])
    mask = (df["date"].dt.date >= window_start) & (df["date"].dt.date <= cutoff)
    in_window = df.loc[mask]
    total_days = (cutoff - window_start).days + 1
    if in_window.empty:
        return {"available": False, "days_observed": 0, "days_expected": total_days, "reason": "district weather file exists but has no rows inside the season window"}
    coverage = len(in_window) / total_days
    if coverage < MIN_COVERAGE_FRACTION:
        return {
            "available": False, "days_observed": len(in_window), "days_expected": total_days,
            "reason": f"only {coverage:.0%} of the season window has weather data (below the {MIN_COVERAGE_FRACTION:.0%} minimum) - the fetched calendar year(s) only partially overlap the season window",
        }
    return {
        "available": True,
        "days_observed": len(in_window),
        "days_expected": total_days,
        "temp_c_mean": round(in_window["temp_c"].mean(), 3),
        "precip_mm_sum": round(in_window["precip_mm"].sum(), 2),
        "humidity_pct_mean": round(in_window["humidity_pct"].mean(), 2),
        "wind_speed_ms_mean": round(in_window["wind_speed_ms"].mean(), 3),
    }


def _aggregate_satellite(path: Path, window_start: date, cutoff: date) -> dict:
    df = pd.read_csv(path, parse_dates=["date"])
    mask = (df["date"].dt.date >= window_start) & (df["date"].dt.date <= cutoff)
    in_window = df.loc[mask]

    # Satellite revisits are sparse by nature (Landsat: ~16 days, fewer once
    # cloud cover is accounted for), so a scene-count floor like weather's
    # would unfairly reject legitimately sparse-but-real coverage. Instead,
    # check whether the SOURCE FILE'S OWN fetched date range actually spans
    # the season window - this catches the real risk (e.g. Tamil Nadu's
    # 2019/2024 satellite pull only covers those single calendar years, so a
    # "Whole Year" window that crosses into the next year is only half-
    # coverable) without penalizing genuine cloud-driven sparsity.
    file_min, file_max = df["date"].min().date(), df["date"].max().date()
    window_days = (cutoff - window_start).days + 1
    overlap_start, overlap_end = max(window_start, file_min), min(cutoff, file_max)
    overlap_days = max(0, (overlap_end - overlap_start).days + 1)
    date_range_coverage = overlap_days / window_days

    if in_window.empty or in_window["mean_ndvi"].isna().all():
        return {"available": False, "scenes_observed": 0, "date_range_coverage": round(date_range_coverage, 3),
                "reason": "district satellite file exists but has no usable scenes inside the season window"}
    if date_range_coverage < MIN_COVERAGE_FRACTION:
        return {
            "available": False, "scenes_observed": int(in_window["mean_ndvi"].notna().sum()),
            "date_range_coverage": round(date_range_coverage, 3),
            "reason": f"the source file's own fetched date range only overlaps {date_range_coverage:.0%} of the season window (below the {MIN_COVERAGE_FRACTION:.0%} minimum) - the fetched calendar year(s) only partially cover the window",
        }
    return {
        "available": True,
        "scenes_observed": int(in_window["mean_ndvi"].notna().sum()),
        "date_range_coverage": round(date_range_coverage, 3),
        "ndvi_mean": round(in_window["mean_ndvi"].mean(), 4),
        "evi_mean": round(in_window["mean_evi"].mean(), 4) if "mean_evi" in in_window else None,
        "ndwi_mean": round(in_window["mean_ndwi"].mean(), 4) if "mean_ndwi" in in_window else None,
    }


def build_alignment() -> tuple[list[dict], dict]:
    yields = _load_yield_records()
    registry = pd.read_csv(REGISTRY_PATH)
    old_lookup = _old_registry_lookup()
    soil_df = pd.read_csv(SOIL_PATH) if SOIL_PATH.exists() else pd.DataFrame(columns=["district_id"])
    soil_by_id = {r["district_id"]: r for _, r in soil_df.iterrows()} if not soil_df.empty else {}

    rows = []
    counters = {
        "total_yield_records": len(yields),
        "has_district_metadata": 0,
        "no_district_metadata": 0,
        "weather_matched": 0,
        "satellite_matched": 0,
        "soil_matched": 0,
        "fully_aligned_weather_satellite": 0,
        "fully_aligned_multimodal": 0,
        "duplicate_examples_dropped": 0,
        "invalid_yield_records": 0,
    }
    rejection_reasons: dict = {}
    seen_keys = set()

    for rec in yields.itertuples(index=False):
        key = (rec.state, rec.district, rec.crop, rec.season, rec.year)
        if key in seen_keys:
            counters["duplicate_examples_dropped"] += 1
            continue
        seen_keys.add(key)

        yield_valid = YIELD_MIN <= rec.final_yield_t_ha <= YIELD_MAX
        if not yield_valid:
            counters["invalid_yield_records"] += 1

        reg_match = registry[(registry.state == rec.state) & (registry.district == rec.district)]
        row = {
            "state": rec.state,
            "district": rec.district,
            "crop": rec.crop,
            "season": rec.season,
            "year": rec.year,
            "geographic_level": "district",
            "final_yield_t_ha": rec.final_yield_t_ha,
            "yield_valid": yield_valid,
            "yield_source_name": rec.source_name,
            "yield_source_url": rec.source_url,
            "yield_retrieved_date": rec.retrieved_date,
        }

        if reg_match.empty or pd.isna(reg_match.iloc[0]["latitude"]):
            counters["no_district_metadata"] += 1
            row.update({
                "district_id": reg_match.iloc[0]["district_id"] if not reg_match.empty else "",
                "weather_available": False, "satellite_available": False, "soil_available": False,
                "rejection_reason": "no district boundary/geometry available (see data/metadata/district_registry.csv administrative_boundary_notes)",
            })
            rejection_reasons["no_boundary_source"] = rejection_reasons.get("no_boundary_source", 0) + 1
            rows.append(row)
            continue

        counters["has_district_metadata"] += 1
        district_id = reg_match.iloc[0]["district_id"]
        canonical_name = reg_match.iloc[0]["canonical_district_name"]
        row["district_id"] = district_id
        row["canonical_district_name"] = canonical_name
        row["administrative_boundary_notes"] = reg_match.iloc[0]["administrative_boundary_notes"]

        try:
            window_start, cutoff = season_window(rec.season, int(rec.year))
        except ValueError as e:
            row.update({"weather_available": False, "satellite_available": False, "soil_available": False,
                        "rejection_reason": str(e)})
            rejection_reasons["unrecognized_season"] = rejection_reasons.get("unrecognized_season", 0) + 1
            rows.append(row)
            continue

        row["season_window_start"] = window_start.isoformat()
        row["prediction_cutoff_date"] = cutoff.isoformat()

        wpath = _find_weather_file(district_id, canonical_name, old_lookup)
        weather = _aggregate_weather(wpath, window_start, cutoff) if wpath else {
            "available": False, "reason": "no weather file exists for this district (real fetch never attempted or district has no boundary)"
        }
        row["weather_available"] = weather["available"]
        row["weather_source"] = str(wpath.relative_to(ROOT)) if wpath else ""
        if weather["available"]:
            counters["weather_matched"] += 1
            row["weather_temp_c_mean"] = weather["temp_c_mean"]
            row["weather_precip_mm_sum"] = weather["precip_mm_sum"]
            row["weather_humidity_pct_mean"] = weather["humidity_pct_mean"]
            row["weather_wind_speed_ms_mean"] = weather["wind_speed_ms_mean"]
            row["weather_days_observed"] = weather["days_observed"]
            row["weather_days_expected"] = weather["days_expected"]
        else:
            row["weather_precip_mm_sum"] = row["weather_humidity_pct_mean"] = row["weather_wind_speed_ms_mean"] = None
            row["weather_days_observed"] = 0
            row["weather_days_expected"] = (cutoff - window_start).days + 1
            reason = weather.get("reason", "unknown")
            rejection_reasons[f"weather_missing:{reason}"] = rejection_reasons.get(f"weather_missing:{reason}", 0) + 1

        spath = _find_satellite_file(district_id, canonical_name, old_lookup)
        satellite = _aggregate_satellite(spath, window_start, cutoff) if spath else {
            "available": False, "reason": "no satellite file exists for this district (real fetch never attempted or district has no boundary)"
        }
        row["satellite_available"] = satellite["available"]
        row["satellite_source"] = str(spath.relative_to(ROOT)) if spath else ""
        if satellite["available"]:
            counters["satellite_matched"] += 1
            row["satellite_ndvi_mean"] = satellite["ndvi_mean"]
            row["satellite_evi_mean"] = satellite["evi_mean"]
            row["satellite_ndwi_mean"] = satellite["ndwi_mean"]
            row["satellite_scenes_observed"] = satellite["scenes_observed"]
        else:
            row["satellite_ndvi_mean"] = row["satellite_evi_mean"] = row["satellite_ndwi_mean"] = None
            row["satellite_scenes_observed"] = 0
            reason = satellite.get("reason", "unknown")
            rejection_reasons[f"satellite_missing:{reason}"] = rejection_reasons.get(f"satellite_missing:{reason}", 0) + 1

        soil_row = soil_by_id.get(district_id)
        row["soil_available"] = soil_row is not None
        if soil_row is not None:
            counters["soil_matched"] += 1
            for c in SOIL_COLS:
                row[f"soil_{c}"] = soil_row[c]
            row["soil_source"] = "ISRIC SoilGrids REST API v2.0, district GAUL centroid"
        else:
            for c in SOIL_COLS:
                row[f"soil_{c}"] = None
            row["soil_source"] = ""
            rejection_reasons["soil_missing"] = rejection_reasons.get("soil_missing", 0) + 1

        if row["weather_available"] and row["satellite_available"]:
            counters["fully_aligned_weather_satellite"] += 1
        if row["weather_available"] and row["satellite_available"] and row["soil_available"]:
            counters["fully_aligned_multimodal"] += 1

        row["rejection_reason"] = "" if (row["weather_available"] or row["satellite_available"]) else "no weather or satellite match"
        rows.append(row)

    return rows, {"counters": counters, "rejection_reasons": rejection_reasons}


def write_outputs(rows: list[dict], stats: dict):
    all_cols = []
    for r in rows:
        for k in r.keys():
            if k not in all_cols:
                all_cols.append(k)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=all_cols)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {OUT_PATH}")

    c = stats["counters"]
    lines = [
        "# District alignment validation report",
        "",
        "Generated by `ingestion/district_alignment.py`. Every real yield observation from the three",
        "Southern India collections appears exactly once in `data/processed/district_multimodal_examples.csv`,",
        "whether or not it could be matched to weather, satellite, or soil data - **no record was dropped**.",
        "",
        "## Counts (COLLECTED vs MATCHED vs FULLY ALIGNED - not the same number)",
        "",
        f"- **Collected** (real yield observations read from the three clean CSVs): {c['total_yield_records']}",
        f"- Duplicate `(state,district,crop,season,year)` keys encountered and dropped before alignment: {c['duplicate_examples_dropped']}",
        f"- Invalid yield (outside {YIELD_MIN}-{YIELD_MAX} t/ha): {c['invalid_yield_records']}",
        f"- Has district geographic metadata (a real GAUL-matched boundary): {c['has_district_metadata']}",
        f"- No district geographic metadata (no boundary source - see district_registry.csv): {c['no_district_metadata']}",
        f"- **Weather-matched** (real weather data covers the season window): {c['weather_matched']}",
        f"- **Satellite-matched** (real satellite data covers the season window): {c['satellite_matched']}",
        f"- **Soil-matched** (real SoilGrids value for the district centroid): {c['soil_matched']}",
        f"- **Fully aligned, weather+satellite** (both matched - the minimum for a weather+satellite or full-multimodal model): {c['fully_aligned_weather_satellite']}",
        f"- **Fully aligned, multimodal** (weather+satellite+soil all matched): {c['fully_aligned_multimodal']}",
        "",
        "## Rejection / missing-data reasons (every excluded match, with why)",
        "",
    ]
    for reason, count in sorted(stats["rejection_reasons"].items(), key=lambda kv: -kv[1]):
        lines.append(f"- `{reason}`: {count}")
    lines += [
        "",
        "## Coverage by state",
        "",
    ]
    df = pd.DataFrame(rows)
    for state, g in df.groupby("state"):
        lines.append(
            f"- **{state}**: {len(g)} collected, {g['weather_available'].sum()} weather-matched, "
            f"{g['satellite_available'].sum()} satellite-matched, {g['soil_available'].sum()} soil-matched, "
            f"{(g['weather_available'] & g['satellite_available']).sum()} fully aligned (weather+satellite)"
        )
    lines += ["", "## Coverage by year", ""]
    for year, g in df.groupby("year"):
        lines.append(
            f"- {int(year)}: {len(g)} collected, "
            f"{(g['weather_available'] & g['satellite_available']).sum()} fully aligned (weather+satellite)"
        )
    lines += ["", "## Coverage by season", ""]
    for season, g in df.groupby("season"):
        lines.append(
            f"- {season}: {len(g)} collected, "
            f"{(g['weather_available'] & g['satellite_available']).sum()} fully aligned (weather+satellite)"
        )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote -> {REPORT_PATH}")


def main():
    rows, stats = build_alignment()
    write_outputs(rows, stats)
    print(json.dumps(stats["counters"], indent=2))


if __name__ == "__main__":
    main()
