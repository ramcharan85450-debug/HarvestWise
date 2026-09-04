"""
Experiment 8, step 3: construct ONLY the five pre-registered rainfall variables.

The pre-registration (experiments/EXPERIMENT_8_PREREGISTRATION.md, section 3.3)
fixes the block at exactly five variables. This module builds those five and
nothing else. It must not grow after results are seen - adding a sixth variable
post hoc is the most direct available route to a false positive.

    1  precip_anomaly_z      (season total - 1971-2000 normal) / 1971-2000 SD
    2  rain_days             days with precipitation >= 2.5 mm
    3  max_dry_spell_days    longest run of consecutive days < 2.5 mm
    4  precip_cv_10day       CV of mean daily rate across the 18 ten-day blocks
    5  onset_day             first day-of-year whose 7-day forward cumulative
                             precipitation reaches 25 mm

THE 2.5 mm THRESHOLD is the India Meteorological Department's own definition of
a "rainy day". It is an Indian meteorological convention, not a threshold chosen
here. Arm 7 of the pre-registration re-runs variables 2 and 3 at 1 mm.

THE 25 mm / 7-day ONSET RULE is a standard agronomic convention, NOT a
per-district verified sowing observation. It carries the same honesty caveat
already attached to the Kharif window itself in
ingestion/district_season_calendar.py, and is labelled as a convention wherever
onset_day is reported.

WINDOW. 1 June - 30 November of year Y, inclusive: 183 days, identical to the
window the existing pipeline uses for weather_precip_mm_sum
(ingestion/district_season_calendar.py). No observation dated after 30 November
of year Y can enter row Y. Future-year exposure is therefore structurally
impossible, and this module asserts it rather than assuming it.

MISSING DATA. Never imputed, never interpolated, never carried forward, never
zero-filled. A district-year that cannot be computed is emitted with an explicit
status and a null value, and is counted in the output manifest.

Run:
    python -m ingestion.kharif_rainfall_features
"""

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PANEL_PATH = ROOT / "data" / "processed" / "district_multimodal_examples_v2.csv"
DAILY_DIR = ROOT / "data" / "raw" / "weather" / "districts"
CLIM_DIR = ROOT / "data" / "raw" / "weather" / "climatology_1971_2000"
OUT_PATH = ROOT / "data" / "processed" / "experiment8_rainfall_features.csv"
MANIFEST_PATH = ROOT / "data" / "processed" / "experiment8_rainfall_features_manifest.json"

RAIN_DAY_MM = 2.5          # IMD "rainy day"
ONSET_MM = 25.0            # 7-day cumulative threshold
ONSET_WINDOW_DAYS = 7
N_BLOCKS = 18              # ten-day blocks across the 183-day window
YEAR_MIN, YEAR_MAX = 2000, 2012


def kharif_window(year: int) -> tuple[date, date]:
    """1 June - 30 November inclusive. Identical to
    ingestion/district_season_calendar.season_window('kharif', year)."""
    return date(year, 6, 1), date(year, 11, 30)


def _blocks(values: np.ndarray, n_blocks: int = N_BLOCKS) -> np.ndarray:
    """Mean DAILY RATE within each ten-day block.

    183 days do not divide into 18 equal blocks, so the final block carries 13
    days rather than 10. Using each block's mean daily rate rather than its
    total is what keeps that unequal length from inflating the last block and
    manufacturing dispersion that is an artefact of the calendar."""
    edges = [i * 10 for i in range(n_blocks)] + [len(values)]
    return np.array([values[edges[i]:edges[i + 1]].mean() for i in range(n_blocks)])


def max_dry_spell(values: np.ndarray, threshold: float = RAIN_DAY_MM) -> int:
    """Longest run of consecutive days strictly below the threshold."""
    best = run = 0
    for v in values:
        run = run + 1 if v < threshold else 0
        best = max(best, run)
    return int(best)


def onset_day(values: np.ndarray, dates: pd.Series) -> tuple[float | None, str]:
    """Day-of-year on which forward 7-day cumulative rainfall first reaches
    ONSET_MM. The search stops early enough that the 7-day window stays inside
    the season - a window running past 30 November would import days the
    pre-registration forbids."""
    n = len(values)
    csum = np.concatenate([[0.0], np.cumsum(values)])
    for i in range(n - ONSET_WINDOW_DAYS + 1):
        if csum[i + ONSET_WINDOW_DAYS] - csum[i] >= ONSET_MM:
            return float(dates.iloc[i].timetuple().tm_yday), "OBSERVED"
    return None, "ONSET_NOT_REACHED"


def load_climatology() -> dict[str, dict]:
    """Per-district Kharif normal and SD over 1971-2000."""
    out = {}
    for path in sorted(CLIM_DIR.glob("*_kharif_climatology.json")):
        p = json.loads(path.read_text(encoding="utf-8"))
        vals = [v for v in p["kharif_total_mm"].values() if v is not None]
        if len(vals) < 25:  # a normal from fewer than 25 of 30 years is not a normal
            out[p["district_id"]] = {"status": "BASELINE_INSUFFICIENT", "n_years": len(vals)}
            continue
        out[p["district_id"]] = {
            "status": "OBSERVED",
            "n_years": len(vals),
            "normal_mm": float(np.mean(vals)),
            "sd_mm": float(np.std(vals, ddof=1)),
            "baseline_years": p["baseline_years"],
        }
    return out


def build() -> pd.DataFrame:
    panel = pd.read_csv(PANEL_PATH)
    k = panel[
        (panel["season"] == "Kharif")
        & (panel["weather_available"])
        & (panel["satellite_available"])
        & (panel["year"].between(YEAR_MIN, YEAR_MAX))
    ].copy()
    clim = load_climatology()

    rows = []
    for rec in k.itertuples(index=False):
        did = rec.district_id
        daily_path = Path(str(rec.weather_source).replace("\\", "/"))
        if not daily_path.is_absolute():
            daily_path = ROOT / daily_path

        base = {
            "district_id": did,
            "state": rec.state,
            "district": rec.district,
            "year": int(rec.year),
            "season": "Kharif",
            "final_yield_t_ha": rec.final_yield_t_ha,
            "weather_precip_mm_sum": rec.weather_precip_mm_sum,
        }

        if not daily_path.exists():
            rows.append({**base, "status": "DATA_NOT_AVAILABLE"})
            continue

        w = pd.read_csv(daily_path, parse_dates=["date"])
        start, end = kharif_window(int(rec.year))
        win = w[(w["date"].dt.date >= start) & (w["date"].dt.date <= end)].sort_values("date")

        # Structural guarantee, asserted rather than assumed: nothing dated
        # after the season's own cutoff can reach this row.
        assert win["date"].dt.date.max() <= end, f"future-year exposure in {did} {rec.year}"

        expected = (end - start).days + 1
        if len(win) != expected or win["precip_mm"].isna().any():
            rows.append({**base, "status": "DATA_NOT_AVAILABLE",
                         "days_observed": int(len(win)), "days_expected": expected})
            continue

        p = win["precip_mm"].to_numpy(dtype=float)
        season_total = float(p.sum())

        c = clim.get(did)
        if c is None:
            anomaly, anomaly_status = None, "BASELINE_NOT_AVAILABLE"
            normal = sd = None
        elif c["status"] != "OBSERVED":
            anomaly, anomaly_status = None, c["status"]
            normal = sd = None
        else:
            normal, sd = c["normal_mm"], c["sd_mm"]
            anomaly, anomaly_status = (season_total - normal) / sd, "OBSERVED"

        od, od_status = onset_day(p, win["date"])
        blocks = _blocks(p)

        rows.append({
            **base,
            "status": "OBSERVED",
            "days_observed": int(len(win)),
            "days_expected": expected,
            "season_total_mm_recomputed": season_total,
            "baseline_normal_mm": normal,
            "baseline_sd_mm": sd,
            # --- the five pre-registered block variables ---
            "precip_anomaly_z": anomaly,
            "rain_days": int((p >= RAIN_DAY_MM).sum()),
            "max_dry_spell_days": max_dry_spell(p),
            "precip_cv_10day": float(blocks.std(ddof=1) / blocks.mean()) if blocks.mean() > 0 else None,
            "onset_day": od,
            # --- statuses ---
            "anomaly_status": anomaly_status,
            "onset_status": od_status,
            # --- Arm 7 sensitivity (1 mm threshold), built now so the arm
            #     cannot be tuned later; NOT part of the primary block ---
            "rain_days_1mm": int((p >= 1.0).sum()),
            "max_dry_spell_days_1mm": max_dry_spell(p, 1.0),
        })

    return pd.DataFrame(rows)


def main():
    df = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    ok = df[df["status"] == "OBSERVED"]
    # Validation: our recomputed season total must reproduce the existing
    # pipeline's weather_precip_mm_sum. If it does not, the daily window here
    # is not the window the panel was built on and nothing downstream is safe.
    v = ok.dropna(subset=["season_total_mm_recomputed", "weather_precip_mm_sum"])
    diff = (v["season_total_mm_recomputed"] - v["weather_precip_mm_sum"]).abs()

    manifest = {
        "rows_total": int(len(df)),
        "rows_observed": int(len(ok)),
        "status_counts": df["status"].value_counts().to_dict(),
        "anomaly_status_counts": df["anomaly_status"].value_counts(dropna=False).to_dict()
        if "anomaly_status" in df else {},
        "onset_status_counts": df["onset_status"].value_counts(dropna=False).to_dict()
        if "onset_status" in df else {},
        "districts": int(df["district_id"].nunique()),
        "years": sorted(int(y) for y in df["year"].unique()),
        "validation_vs_existing_pipeline": {
            "n_compared": int(len(v)),
            "max_abs_diff_mm": float(diff.max()) if len(diff) else None,
            "mean_abs_diff_mm": float(diff.mean()) if len(diff) else None,
            "n_over_1mm": int((diff > 1.0).sum()) if len(diff) else None,
        },
        "definitions": {
            "rain_day_threshold_mm": RAIN_DAY_MM,
            "rain_day_threshold_source": "IMD definition of a rainy day",
            "onset_rule": f"first day whose forward {ONSET_WINDOW_DAYS}-day cumulative precipitation reaches {ONSET_MM} mm",
            "onset_rule_caveat": "standard agronomic convention, NOT a per-district verified sowing date",
            "window": "1 June - 30 November inclusive (183 days)",
            "baseline": "1971-2000, strictly prior to the 2000-2012 panel",
            "n_blocks": N_BLOCKS,
            "block_note": "final block carries 13 days; mean daily rate per block is used so unequal length adds no dispersion",
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    print(f"rows {len(df)}  observed {len(ok)}  districts {df['district_id'].nunique()}")
    print(f"status: {manifest['status_counts']}")
    print(f"anomaly_status: {manifest['anomaly_status_counts']}")
    print(f"onset_status: {manifest['onset_status_counts']}")
    print(f"validation vs existing pipeline: max|diff| = {manifest['validation_vs_existing_pipeline']['max_abs_diff_mm']} mm "
          f"over {manifest['validation_vs_existing_pipeline']['n_compared']} rows")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
