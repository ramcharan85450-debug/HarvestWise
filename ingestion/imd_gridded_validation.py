"""
Experiment 8, step 9: independent validation of the ERA5-Land rainfall series
against IMD's official gridded product.

WHY. ERA5-Land is a REANALYSIS (Tier 2 under the project source hierarchy) -
a physical model constrained by observations, not a gauge network. The whole
Experiment 8 design rests on rainfall being measured identically across Andhra
Pradesh, Telangana and Tamil Nadu; that is the property whose absence made
Experiment 7 not feasible. A single product cannot demonstrate its own
regional evenness. IMD's gridded rainfall is Tier 1 official, is built from a
gauge network by a different institution with a different method, and covers
the full window - so agreement between the two is real evidence, and
region-patterned DISagreement is a real warning.

IMD remains a CROSS-CHECK, not a replacement. ERA5-Land stays primary because
its district aggregation is already implemented, documented and reproducible
here (ingestion/district_weather_pull.py); swapping in IMD would introduce a
new aggregation whose only validation would be the very comparison being made.

SOURCE
    India Meteorological Department, Pune
    Gridded Rainfall (0.25 x 0.25 degree) daily binary
    https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_Bin.html
    POST rain=<year> to rainfall.php  ->  ind<year>_rfp25.grd

FORMAT (verified empirically, not assumed)
    float32 little-endian, shape (days, 129 lat, 135 lon)
    lat  6.5 .. 38.5 at 0.25 deg   (129 points)
    lon 66.5 .. 100.0 at 0.25 deg  (135 points)
    missing = -999.0, never treated as zero

AGGREGATION. District polygons are exported from the same Earth Engine
geometries the ERA5-Land pull used, so both products are reduced over
IDENTICAL boundaries. An IMD grid cell contributes to a district when its
centre falls inside the polygon. A district containing no cell centre - IMD's
0.25 deg cell is ~28 km, larger than the smallest districts here - is recorded
with an explicit CELL_FALLBACK_NEAREST status and the nearest cell to its
centroid is used; that status is reported, never silently absorbed.

Run:
    python -m ingestion.imd_gridded_validation
"""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import urllib3

urllib3.disable_warnings()

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "data" / "metadata" / "district_registry.csv"
PANEL_PATH = ROOT / "data" / "processed" / "experiment8_rainfall_panel.csv"
GRID_DIR = ROOT / "data" / "raw" / "weather" / "imd_gridded"
POLY_DIR = ROOT / "data" / "metadata" / "boundary_sources" / "district_polygons_ee"
OUT_PATH = ROOT / "data" / "processed" / "experiment8_imd_validation.csv"
REPORT_PATH = ROOT / "experiments" / "experiment8_imd_validation.json"

FORM_URL = "https://www.imdpune.gov.in/cmpg/Griddata/rainfall.php"
PAGE_URL = "https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_Bin.html"
NLAT, NLON = 129, 135
LAT0, LON0, STEP = 6.5, 66.5, 0.25
MISSING = -999.0
YEARS = list(range(2000, 2013))


def export_polygons(district_ids: list[str]) -> None:
    """One GeoJSON per district, taken from the SAME Earth Engine geometry the
    ERA5-Land pull reduced over. Cached; re-running is free."""
    import ee
    from ingestion.district_env_pull import _resolve_geometry
    from ingestion.landsat_fetch import EE_PROJECT_ID

    POLY_DIR.mkdir(parents=True, exist_ok=True)
    todo = [d for d in district_ids if not (POLY_DIR / f"{d}.geojson").exists()]
    if not todo:
        return
    ee.Initialize(project=EE_PROJECT_ID)
    reg = pd.read_csv(REGISTRY_PATH)
    for rec in reg[reg["district_id"].isin(todo)].itertuples(index=False):
        geom = _resolve_geometry(rec)
        gj = geom.simplify(maxError=500).getInfo()
        (POLY_DIR / f"{rec.district_id}.geojson").write_text(json.dumps(gj), encoding="utf-8")
        print(f"  polygon {rec.district_id} {rec.district}")


def download_year(year: int, session: requests.Session) -> Path:
    path = GRID_DIR / f"imd_rain_{year}.grd"
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    GRID_DIR.mkdir(parents=True, exist_ok=True)
    r = session.post(FORM_URL, data={"rain": str(year)}, timeout=300, verify=False)
    r.raise_for_status()
    path.write_bytes(r.content)
    return path


def read_year(path: Path, year: int) -> np.ndarray:
    a = np.fromfile(path, dtype="<f4")
    ndays = a.size // (NLAT * NLON)
    expected = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
    if ndays != expected:
        raise ValueError(f"{path.name}: {ndays} days, expected {expected}")
    return a.reshape(ndays, NLAT, NLON)


def _rings(gj: dict) -> list:
    """Outer rings of a geometry. Earth Engine returns a GeometryCollection for
    districts whose boundary it stores as several parts (islands, exclaves), so
    that case is unwrapped recursively rather than rejected - dropping those
    districts would silently thin the very coverage this check is measuring."""
    t = gj["type"]
    if t == "GeometryCollection":
        return [r for g in gj["geometries"] for r in _rings(g)]
    c = gj.get("coordinates")
    if c is None:
        return []
    if t == "Polygon":
        return [c[0]]
    if t == "MultiPolygon":
        return [p[0] for p in c]
    if t in ("Point", "LineString", "LinearRing", "MultiPoint"):
        return []  # degenerate parts carry no area; they contribute no cells
    raise ValueError(f"unsupported geometry {t}")


def _inside(lon: float, lat: float, rings: list) -> bool:
    """Ray casting. A point inside any outer ring counts as inside; holes are
    not modelled, which for Indian district boundaries is immaterial at a
    0.25 degree cell size."""
    for ring in rings:
        n, ins = len(ring), False
        for i in range(n):
            x1, y1 = ring[i][0], ring[i][1]
            x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
            if (y1 > lat) != (y2 > lat):
                xin = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
                if lon < xin:
                    ins = not ins
        if ins:
            return True
    return False


def district_cells(district_id: str, centroid: tuple[float, float]) -> tuple[list[tuple[int, int]], str]:
    gj = json.loads((POLY_DIR / f"{district_id}.geojson").read_text(encoding="utf-8"))
    rings = _rings(gj)
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    cells = []
    i0 = max(0, int((min(ys) - LAT0) / STEP) - 1); i1 = min(NLAT, int((max(ys) - LAT0) / STEP) + 2)
    j0 = max(0, int((min(xs) - LON0) / STEP) - 1); j1 = min(NLON, int((max(xs) - LON0) / STEP) + 2)
    for i in range(i0, i1):
        for j in range(j0, j1):
            if _inside(LON0 + j * STEP, LAT0 + i * STEP, rings):
                cells.append((i, j))
    if cells:
        return cells, "OBSERVED"
    lon_c, lat_c = centroid
    return [(int(round((lat_c - LAT0) / STEP)), int(round((lon_c - LON0) / STEP)))], "CELL_FALLBACK_NEAREST"


def kharif_slice(year: int) -> tuple[int, int]:
    """Day indices for 1 June - 30 November inclusive, 0-based."""
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    start = 152 if leap else 151
    return start, start + 183


def main():
    panel = pd.read_csv(PANEL_PATH)
    reg = pd.read_csv(REGISTRY_PATH).set_index("district_id")
    dids = sorted(panel["district_id"].unique())
    print(f"districts: {len(dids)}")

    export_polygons(dids)

    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": PAGE_URL})
    grids = {}
    for y in YEARS:
        p = download_year(y, s)
        grids[y] = read_year(p, y)
        print(f"  IMD {y}: {grids[y].shape} ({p.stat().st_size/1e6:.1f} MB)")

    cellmap = {}
    for d in dids:
        r = reg.loc[d]
        cellmap[d] = district_cells(d, (float(r["longitude"]), float(r["latitude"])))

    rows = []
    for d in dids:
        cells, cstat = cellmap[d]
        ii = np.array([c[0] for c in cells]); jj = np.array([c[1] for c in cells])
        for y in YEARS:
            a, b = kharif_slice(y)
            sub = grids[y][a:b, ii, jj]                  # (183, ncells)
            valid = sub > MISSING / 2
            if not valid.all():
                # a cell with any missing day cannot give a season total
                keep = valid.all(axis=0)
                if not keep.any():
                    rows.append({"district_id": d, "year": y, "imd_kharif_mm": None,
                                 "n_cells": len(cells), "cell_status": cstat,
                                 "imd_status": "DATA_NOT_AVAILABLE"})
                    continue
                sub = sub[:, keep]
            rows.append({"district_id": d, "year": y,
                         "imd_kharif_mm": float(sub.sum(axis=0).mean()),
                         "n_cells": int(sub.shape[1]), "cell_status": cstat, "imd_status": "OBSERVED"})

    imd = pd.DataFrame(rows)
    m = panel.merge(imd, on=["district_id", "year"], how="left")
    m.to_csv(OUT_PATH, index=False)

    ok = m[(m["imd_status"] == "OBSERVED") & m["imd_kharif_mm"].notna() & m["in_analytic_sample"]]
    report = {
        "source": {"institution": "India Meteorological Department, Pune",
                   "product": "Gridded Rainfall 0.25 x 0.25 degree daily binary",
                   "url": PAGE_URL, "years": YEARS, "tier": "Tier 1 official"},
        "role": "independent cross-check; ERA5-Land remains the primary source",
        "n_compared": int(len(ok)),
        "cell_status_counts": m["cell_status"].value_counts().to_dict(),
        "imd_status_counts": m["imd_status"].value_counts(dropna=False).to_dict(),
        "overall": {
            "pearson_r": float(ok["imd_kharif_mm"].corr(ok["season_total_mm_recomputed"])),
            "mean_bias_era5_minus_imd_mm": float((ok["season_total_mm_recomputed"] - ok["imd_kharif_mm"]).mean()),
            "mean_abs_diff_mm": float((ok["season_total_mm_recomputed"] - ok["imd_kharif_mm"]).abs().mean()),
        },
        "by_region": {},
    }
    for st, g in ok.groupby("state"):
        report["by_region"][st] = {
            "n": int(len(g)),
            "pearson_r": float(g["imd_kharif_mm"].corr(g["season_total_mm_recomputed"])),
            "mean_bias_era5_minus_imd_mm": float((g["season_total_mm_recomputed"] - g["imd_kharif_mm"]).mean()),
            "mean_abs_diff_mm": float((g["season_total_mm_recomputed"] - g["imd_kharif_mm"]).abs().mean()),
            "imd_mean_mm": float(g["imd_kharif_mm"].mean()),
            "era5_mean_mm": float(g["season_total_mm_recomputed"].mean()),
        }
    # within-district correlation: does the product agree on YEAR-TO-YEAR
    # movement, which is what the experiment actually identifies from?
    w = ok.copy()
    for c in ["imd_kharif_mm", "season_total_mm_recomputed"]:
        w[c + "_dm"] = w[c] - w.groupby("district_id")[c].transform("mean")
    report["within_district_pearson_r"] = float(w["imd_kharif_mm_dm"].corr(w["season_total_mm_recomputed_dm"]))
    report["within_district_pearson_r_by_region"] = {
        st: float(g["imd_kharif_mm_dm"].corr(g["season_total_mm_recomputed_dm"]))
        for st, g in w.groupby("state")}

    REPORT_PATH.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    print(f"\nwrote {OUT_PATH}\nwrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
