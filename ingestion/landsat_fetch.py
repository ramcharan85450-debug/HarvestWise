"""
Landsat vegetation-index time series from Google Earth Engine.

Why Landsat and not Sentinel-2: the district-level yield labels this project
now depends on (data.gov.in resource 35be999b-..., see
ingestion/datagovin_fetch.py) cover **1997-2015**, and Sentinel-2 surface
reflectance only begins in 2017 - there is zero overlap. Landsat covers the
whole label range:

    LANDSAT/LT05/C02/T1_L2   Landsat 5 TM      1984-2012
    LANDSAT/LE07/C02/T1_L2   Landsat 7 ETM+    1999-2022  (SLC-off gaps after 2003-05)
    LANDSAT/LC08/C02/T1_L2   Landsat 8 OLI     2013-
    LANDSAT/LC09/C02/T1_L2   Landsat 9 OLI-2   2021-

Trade-off, stated rather than hidden: Landsat is 30 m and revisits every 16
days, against Sentinel-2's 10 m and 5 days. For a label that is itself a
district-wide average this is an appropriate resolution - arguably better
matched than 10 m pixels aggregated to a whole district - but it is a real
difference from the 7-field Sentinel-2 data, and results from the two sources
must not be pooled without saying so.

Band harmonisation is the part that is easy to get silently wrong. TM/ETM+
and OLI number their bands differently for the SAME wavelengths:

                     Blue     Red      NIR      SWIR1
    L5/L7 (TM/ETM+)  SR_B1    SR_B3    SR_B4    SR_B5
    L8/L9 (OLI)      SR_B2    SR_B4    SR_B5    SR_B6

Computing NDVI from "SR_B4 and SR_B3" across both sensors would silently
compute NIR/RED on one and RED/GREEN on the other. Every collection here is
renamed to BLUE/RED/NIR/SWIR1 before any index is computed.

Setup:
    pip install earthengine-api
    earthengine authenticate
"""

import csv
from pathlib import Path

import ee

from ingestion.config import MAX_CLOUD_COVER_PCT, RAW_DIR

SATELLITE_DIR = RAW_DIR / "satellite"
EE_PROJECT_ID = "harvestwise-project"

# Collection id -> (blue, red, nir, swir1) in that collection's own band names.
LANDSAT_COLLECTIONS = {
    "LANDSAT/LT05/C02/T1_L2": ("SR_B1", "SR_B3", "SR_B4", "SR_B5"),
    "LANDSAT/LE07/C02/T1_L2": ("SR_B1", "SR_B3", "SR_B4", "SR_B5"),
    "LANDSAT/LC08/C02/T1_L2": ("SR_B2", "SR_B4", "SR_B5", "SR_B6"),
    "LANDSAT/LC09/C02/T1_L2": ("SR_B2", "SR_B4", "SR_B5", "SR_B6"),
}

# Collection 2 Level-2 surface reflectance is stored as scaled integers.
# Real reflectance = DN * 0.0000275 - 0.2. Skipping this does not just change
# units - EVI's formula has additive constants (+1, -7.5*BLUE), so feeding it
# raw DNs produces a number that is not EVI at all.
SR_SCALE, SR_OFFSET = 0.0000275, -0.2


def _mask_clouds(image: "ee.Image") -> "ee.Image":
    """QA_PIXEL bitmask: bit 1 dilated cloud, 3 cloud, 4 cloud shadow, 5 snow."""
    qa = image.select("QA_PIXEL")
    mask = (
        qa.bitwiseAnd(1 << 1).eq(0)
        .And(qa.bitwiseAnd(1 << 3).eq(0))
        .And(qa.bitwiseAnd(1 << 4).eq(0))
        .And(qa.bitwiseAnd(1 << 5).eq(0))
    )
    return image.updateMask(mask)


def _harmonized(collection_id: str) -> "ee.ImageCollection":
    blue, red, nir, swir1 = LANDSAT_COLLECTIONS[collection_id]

    def prep(image):
        scaled = (
            image.select([blue, red, nir, swir1])
            .multiply(SR_SCALE)
            .add(SR_OFFSET)
            .rename(["BLUE", "RED", "NIR", "SWIR1"])
        )
        return scaled.copyProperties(image, ["system:time_start", "CLOUD_COVER"])

    return ee.ImageCollection(collection_id).map(_mask_clouds).map(prep)


def _with_indices(image: "ee.Image") -> "ee.Image":
    ndvi = image.normalizedDifference(["NIR", "RED"]).rename("NDVI")
    evi = image.expression(
        "2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)",
        {"NIR": image.select("NIR"), "RED": image.select("RED"), "BLUE": image.select("BLUE")},
    ).rename("EVI")
    # NDWI (Gao 1996), NIR/SWIR - vegetation water content, the drought-stress
    # signal. Same definition as the Sentinel-2 path uses (B8/B11), so the two
    # sources produce a comparable NDWI.
    ndwi = image.normalizedDifference(["NIR", "SWIR1"]).rename("NDWI")
    return image.addBands([ndvi, evi, ndwi])


def landsat_collection(start_date: str, end_date: str, region: "ee.Geometry") -> "ee.ImageCollection":
    """Merges every Landsat mission covering the window into one harmonised,
    cloud-masked collection carrying NDVI/EVI/NDWI."""
    merged = None
    for cid in LANDSAT_COLLECTIONS:
        coll = (
            _harmonized(cid)
            .filterBounds(region)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lte("CLOUD_COVER", MAX_CLOUD_COVER_PCT))
        )
        merged = coll if merged is None else merged.merge(coll)
    return merged.map(_with_indices).sort("system:time_start")


# MODIS land cover, IGBP scheme. Class 12 = Croplands, class 14 =
# Cropland/Natural-vegetation mosaic. Covers 2001-2022, which brackets the
# 2000-2012 district window.
MODIS_LANDCOVER = "MODIS/061/MCD12Q1"
CROPLAND_CLASSES = [12, 14]


def cropland_mask_for(image: "ee.Image") -> "ee.Image":
    """A 1/0 cropland mask for the land-cover year matching `image`.

    This is not a refinement, it is required for the district data to mean
    anything. A district polygon is 10^3-10^4 km^2 and contains cities,
    forest, water and every other crop; rice may be a fifth of it. Averaging
    NDVI over the whole polygon and regressing it on a RICE yield label
    dilutes the signal with land that has no bearing on the label - the
    district-scale equivalent of the label-granularity mismatch this whole
    dataset switch exists to fix.

    The year is resolved server-side from the image's own timestamp and
    clamped into the collection's 2001-2022 range, so land-cover change across
    a 13-year window is tracked rather than frozen at one snapshot.
    """
    year = ee.Number(ee.Date(image.get("system:time_start")).get("year")).max(2001).min(2022)
    lc = (
        ee.ImageCollection(MODIS_LANDCOVER)
        .filter(ee.Filter.calendarRange(year, year, "year"))
        .first()
        .select("LC_Type1")
    )
    return lc.eq(CROPLAND_CLASSES[0]).Or(lc.eq(CROPLAND_CLASSES[1]))


def cropland_mask_year(year: int) -> "ee.Image":
    """Cropland mask for a single land-cover year, resolved client-side.

    Preferred over cropland_mask_for() for a multi-year pull: resolving the
    land-cover image once and reusing it costs one lookup, whereas the
    per-image version repeats a filtered collection lookup inside the server
    -side map and measured ~7x slower (3s -> 21s for a two-year district
    pull, which extrapolates to ~14 hours across 417 districts instead of
    ~9). The cost of the simplification is that land-cover change within the
    window is not tracked; MODIS cropland extent moves slowly enough over
    2000-2012 that a mid-period snapshot is a reasonable stand-in, and it is
    a documented approximation rather than a silent one.
    """
    year = max(2001, min(2022, year))
    lc = (
        ee.ImageCollection(MODIS_LANDCOVER)
        .filter(ee.Filter.calendarRange(year, year, "year"))
        .first()
        .select("LC_Type1")
    )
    return lc.eq(CROPLAND_CLASSES[0]).Or(lc.eq(CROPLAND_CLASSES[1]))


def fetch_vegetation_indices(
    geometry, start_date: str, end_date: str, scale: int = 30, cropland_mask: "ee.Image | None" = None
) -> list[dict]:
    """Per-scene mean NDVI/EVI/NDWI over `geometry`. `geometry` may be a
    GeoJSON-style coordinate list or an ee.Geometry (district polygons come in
    as the latter).

    cropland_mask, when given, restricts the average to farmland pixels - pass
    cropland_mask_year(mid_year). Every district-scale pull needs it: a
    district is 10^3-10^4 km^2 and East Godavari, for example, is only 38%
    cropland, so an unmasked average regresses a rice label on mostly
    non-rice land. Leave it None for the original 7 field polygons, which are
    already entirely farmland and smaller than one 500 m MODIS pixel.
    """
    region = geometry if isinstance(geometry, ee.Geometry) else ee.Geometry.Polygon(geometry)
    collection = landsat_collection(start_date, end_date, region)

    def _reduce(image):
        indices = image.select(["NDVI", "EVI", "NDWI"])
        if cropland_mask is not None:
            indices = indices.updateMask(cropland_mask)
        stats = indices.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=scale, maxPixels=1e9, bestEffort=True
        )
        return ee.Feature(
            None,
            {
                "date": image.date().format("YYYY-MM-dd"),
                "mean_ndvi": stats.get("NDVI"),
                "mean_evi": stats.get("EVI"),
                "mean_ndwi": stats.get("NDWI"),
                "cloud_cover_pct": image.get("CLOUD_COVER"),
            },
        )

    features = collection.map(_reduce).filter(ee.Filter.notNull(["mean_ndvi"]))
    return [f["properties"] for f in features.getInfo()["features"]]


def write_csv(rows: list[dict], out_path: Path) -> Path:
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["date", "mean_ndvi", "mean_evi", "mean_ndwi", "cloud_cover_pct"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def main():
    """Smoke test against one of the existing 7 fields, over the Landsat-8 era.

    This deliberately re-pulls a field the project already has Sentinel-2 data
    for, so the two sources can be compared on the same polygon before any
    district-scale ingestion is trusted."""
    from ingestion.config import FIELDS

    ee.Initialize(project=EE_PROJECT_ID)
    field = FIELDS[3]  # F004, Ajnala/Amritsar - Punjab rice
    print(f"Landsat smoke test: {field['field_id']} ({field['name']}) 2013-2015")
    rows = fetch_vegetation_indices(field["geometry"], "2013-01-01", "2015-12-31")
    out = write_csv(rows, SATELLITE_DIR / f"{field['field_id']}_landsat_ndvi.csv")
    print(f"  {len(rows)} scenes -> {out}")
    if rows:
        ndvis = [r["mean_ndvi"] for r in rows if r["mean_ndvi"] is not None]
        print(f"  NDVI range {min(ndvis):.3f} to {max(ndvis):.3f} (expect roughly 0.1-0.9 for cropland)")


if __name__ == "__main__":
    main()
