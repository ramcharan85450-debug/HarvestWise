"""
Central ingestion config. Edit FIELDS and the date range for your actual
crop/region before running any fetch script - everything else reads from here.
"""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
SPLITS_DIR = ROOT_DIR / "data" / "splits"

for d in (RAW_DIR / "satellite", RAW_DIR / "weather", RAW_DIR / "soil", RAW_DIR / "harvest_outcomes", PROCESSED_DIR, SPLITS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Historical window to pull. Widened from 2022 back to 2019 because 4 years
# was the binding constraint on the Climate-Shock Benchmark: with only 4
# seasons per field, just 4 field-seasons crossed the anomaly thresholds
# (see evaluation/climate_shock_benchmark/derive_labels.py), which is far too
# few to be statistically powered, AND each field's "normal" climatology
# baseline was being estimated from the same handful of seasons being
# classified against it. 2019-2025 gives ~7 seasons per field.
#
# Cost of widening further: ERA5 is one CDS request per field per year at
# ~4-5 min of queue time each, so each additional year adds ~30 min of
# background download across 7 fields. Sentinel-2 (Earth Engine) and
# SoilGrids are not affected - they fetch the whole range in one call.
START_DATE = "2019-01-01"
END_DATE = "2025-12-31"

# One entry per field you're tracking. field_id must match the IDs used in
# backend/app/services/data_service.py so the served dashboard and the real
# training data line up. `geometry` is a GeoJSON-style polygon
# [[[lon, lat], [lon, lat], ...]].
#
# These three are REAL, NAMED paddy-growing localities within Coimbatore
# district, Tamil Nadu (Sulur, Kinathukadavu, Annur - all real places with
# known irrigated rice cultivation) - but the polygons themselves are
# representative ~1km boxes centered on each town, NOT GPS-surveyed exact
# farm boundaries. Replace with your actual field boundaries (draw them in
# Google Earth Engine's code editor geometry tool, or export from a
# farm-boundary shapefile with geopandas) when you have them.
FIELDS = [
    {
        "field_id": "F001",
        "name": "Sulur - Rice",
        "crop": "rice",
        "geometry": [[[77.115, 11.015], [77.135, 11.015], [77.135, 11.035], [77.115, 11.035], [77.115, 11.015]]],
    },
    {
        "field_id": "F002",
        "name": "Kinathukadavu - Rice",
        "crop": "rice",
        "geometry": [[[77.000, 10.780], [77.020, 10.780], [77.020, 10.800], [77.000, 10.800], [77.000, 10.780]]],
    },
    {
        "field_id": "F003",
        "name": "Annur - Rice",
        "crop": "rice",
        "geometry": [[[77.097, 11.216], [77.117, 11.216], [77.117, 11.236], [77.097, 11.236], [77.097, 11.216]]],
    },
    # Multi-state expansion: real, named rice-growing localities in 3 more
    # major rice-producing states, same representative-~1km-box caveat as
    # the Coimbatore fields above (not GPS-surveyed farm boundaries).
    {
        "field_id": "F004",
        "name": "Ajnala, Amritsar - Rice",
        "crop": "rice_punjab",
        "geometry": [[[74.755, 31.836], [74.775, 31.836], [74.775, 31.856], [74.755, 31.856], [74.755, 31.836]]],
    },
    {
        "field_id": "F005",
        "name": "Burdwan - Rice",
        "crop": "rice_west_bengal",
        "geometry": [[[87.852, 23.222], [87.872, 23.222], [87.872, 23.242], [87.852, 23.242], [87.852, 23.222]]],
    },
    {
        "field_id": "F006",
        "name": "Amalapuram, East Godavari - Rice",
        "crop": "rice_andhra_pradesh",
        "geometry": [[[81.996, 16.569], [82.016, 16.569], [82.016, 16.589], [81.996, 16.589], [81.996, 16.569]]],
    },
    # Second real crop, same real field as F004: Punjab genuinely runs a
    # rice (kharif) / wheat (rabi) rotation on the same land - this is the
    # actual physical field, not a fabricated duplicate. Reuses F004's
    # already-fetched satellite/weather data (same polygon, full-year date
    # range already covers the rabi wheat season) rather than re-querying
    # GEE/CDS for an identical bounding box - see ingestion/README or the
    # multi-crop-expansion notes for how the raw files were copied over.
    {
        "field_id": "F007",
        "name": "Ajnala, Amritsar - Wheat",
        "crop": "wheat_punjab",
        "geometry": [[[74.755, 31.836], [74.775, 31.836], [74.775, 31.856], [74.755, 31.856], [74.755, 31.836]]],
    },
]

# Scene-level cloud cover ceiling. This is a SECOND filter on top of the
# per-pixel cloud masking that ingestion/satellite_fetch.py already applies via
# Sentinel-2's SCL band (and landsat_fetch.py via QA_PIXEL), so a strict value
# here discards scenes twice over: a 45%-cloudy scene may still have a
# completely clear view of one 450 ha field, and the per-pixel mask would
# handle any cloud that does overlap it.
#
# At the previous value of 20 the cost was severe and invisible: only 44% of
# aligned weekly rows came from a real observation, the other 56% being
# produced by align_pipeline.py's gap interpolation (69% interpolated for F001
# and F003). Whole 20-week seasons came out dead flat - F001's 2022 season
# read NDVI 0.30 for every week - and 20 of 43 season examples "peaked" in
# their final three weeks, which is phenologically impossible. The vegetation
# modality, the centrepiece of the multimodal claim, was mostly manufactured.
#
# 70 keeps the per-pixel mask as the real quality control and lets partly
# cloudy scenes contribute the pixels they do have.
MAX_CLOUD_COVER_PCT = 70

# Approximate crop calendar per crop type: (planting_month, planting_day, season_length_weeks).
# Used by ingestion/align_pipeline.py to estimate growth stage (0=planting, 1=maturity)
# for each week of aligned data, which feeds the phenology-aware fusion gate. Replace
# with your region's actual agronomic calendar / real planting-date records once available.
CROP_CALENDARS = {
    "wheat": {"planting_month": 11, "planting_day": 1, "season_length_weeks": 20},
    "maize": {"planting_month": 6, "planting_day": 15, "season_length_weeks": 18},
    # Samba/Thaladi season - the dominant rice season in Coimbatore district by
    # area (733 of 861 total rice hectares in the 2019-20 season crop report,
    # see data/raw/yield_labels/README - Kar/Kuruvai and Navarai are minor by
    # comparison). Long-duration transplanted rice, ~August planting through
    # January harvest.
    "rice": {"planting_month": 8, "planting_day": 1, "season_length_weeks": 22},
    # Punjab: transplanting is legally restricted to start mid-June (Punjab
    # Preservation of Subsoil Water Act, groundwater conservation), harvest
    # ~October - general agronomic knowledge, not a cited government
    # calendar document; replace with a verified source if precision matters.
    "rice_punjab": {"planting_month": 6, "planting_day": 15, "season_length_weeks": 18},
    # West Bengal: Aman (main, kharif) season - nursery June, transplant
    # July, harvest Nov-Dec.
    "rice_west_bengal": {"planting_month": 7, "planting_day": 1, "season_length_weeks": 20},
    # Andhra Pradesh, Godavari delta: kharif ("Peddha Panta") transplant
    # June-July, harvest Nov-Dec.
    "rice_andhra_pradesh": {"planting_month": 7, "planting_day": 1, "season_length_weeks": 20},
    # Punjab rabi wheat: sown Nov 1-15, harvested ~April - the second crop
    # in the same field's rice-wheat rotation (see F007 in FIELDS above).
    "wheat_punjab": {"planting_month": 11, "planting_day": 1, "season_length_weeks": 20},
}
