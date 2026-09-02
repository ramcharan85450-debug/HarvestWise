"""
Pulls Sentinel-2 vegetation index time series per field from Google Earth
Engine: NDVI (general vegetation vigor), EVI (improved sensitivity in dense
canopy, less saturation than NDVI), and NDWI (vegetation water content -
useful signal for drought stress, distinct from what NDVI/EVI capture).

Setup (one-time):
    pip install earthengine-api
    earthengine authenticate          # opens a browser, logs into your GEE account
    # or, non-interactively:
    python -c "import ee; ee.Authenticate()"

Then, per field, this computes cloud-masked per-scene index values and
exports them as a CSV of (date, mean_ndvi, mean_evi, mean_ndwi,
cloud_cover_pct) rather than downloading full imagery tiles - far cheaper on
a student GEE quota, and enough for the vision encoder in
models/encoders/vision_encoder.py, which trains on this index time series,
not raw multispectral bands.

If you need actual image tiles (for a CNN/ViT encoder on raw pixels instead
of scalar indices), see export_tile() below - it exports GeoTIFFs to your
Earth Engine-linked Google Drive, which you then sync into data/raw/satellite/.

Run:
    python -m ingestion.satellite_fetch
"""

import csv

import ee

from ingestion.config import END_DATE, FIELDS, MAX_CLOUD_COVER_PCT, RAW_DIR, START_DATE

SATELLITE_DIR = RAW_DIR / "satellite"


def _mask_clouds(image: "ee.Image") -> "ee.Image":
    scl = image.select("SCL")
    # SCL classes 3 (cloud shadow), 8/9 (cloud medium/high prob), 10 (cirrus) are masked out
    mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return image.updateMask(mask)


def _with_indices(image: "ee.Image") -> "ee.Image":
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")

    # EVI: reduces saturation in dense canopy and atmospheric noise sensitivity
    # that plain NDVI has - standard MODIS/Sentinel-2 EVI coefficients.
    evi = image.expression(
        "2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)",
        {
            "NIR": image.select("B8").divide(10000),
            "RED": image.select("B4").divide(10000),
            "BLUE": image.select("B2").divide(10000),
        },
    ).rename("EVI")

    # NDWI (Gao, 1996) using NIR/SWIR: vegetation water content, a distinct
    # drought-stress signal from NDVI/EVI (which track chlorophyll/canopy
    # density, not moisture directly).
    ndwi = image.normalizedDifference(["B8", "B11"]).rename("NDWI")

    return image.addBands([ndvi, evi, ndwi])


def fetch_vegetation_indices(field_id: str, geometry: list) -> list[dict]:
    region = ee.Geometry.Polygon(geometry)

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(START_DATE, END_DATE)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD_COVER_PCT))
        .map(_mask_clouds)
        .map(_with_indices)
    )

    def _reduce(image):
        stats = image.select(["NDVI", "EVI", "NDWI"]).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=10, maxPixels=1e9
        )
        cloud_pct = image.get("CLOUDY_PIXEL_PERCENTAGE")
        return ee.Feature(
            None,
            {
                "date": image.date().format("YYYY-MM-dd"),
                "mean_ndvi": stats.get("NDVI"),
                "mean_evi": stats.get("EVI"),
                "mean_ndwi": stats.get("NDWI"),
                "cloud_cover_pct": cloud_pct,
            },
        )

    features = collection.map(_reduce).filter(ee.Filter.notNull(["mean_ndvi"]))
    rows = features.getInfo()["features"]
    return [row["properties"] for row in rows]


def export_tile(field_id: str, geometry: list, date_str: str, drive_folder: str = "harvestwise_tiles"):
    """Optional: export a raw multispectral GeoTIFF for one date to Google Drive,
    if the encoder needs real image tiles rather than the NDVI scalar series."""
    region = ee.Geometry.Polygon(geometry)
    image = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(date_str, ee.Date(date_str).advance(1, "day"))
        .first()
        .select(["B2", "B3", "B4", "B8"])
    )
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=f"{field_id}_{date_str}",
        folder=drive_folder,
        region=region,
        scale=10,
        maxPixels=1e9,
    )
    task.start()
    return task


EE_PROJECT_ID = "harvestwise-project"


def main():
    ee.Initialize(project=EE_PROJECT_ID)

    for field in FIELDS:
        print(f"Fetching vegetation indices for {field['field_id']} ({field['name']})...")
        rows = fetch_vegetation_indices(field["field_id"], field["geometry"])
        out_path = SATELLITE_DIR / f"{field['field_id']}_ndvi.csv"
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "mean_ndvi", "mean_evi", "mean_ndwi", "cloud_cover_pct"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"  wrote {len(rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
