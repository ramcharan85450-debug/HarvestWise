"""
Field registry and shared data access for the serving layer.

The field list is derived from ingestion/config.py's FIELDS - the single
source of truth the whole research pipeline reads - rather than being
maintained separately here. It used to be a hand-written list of three
"Nashik, MH wheat/maize" fields that no longer corresponded to anything the
project actually ingests, trains on, or evaluates, so the dashboard was
describing a different experiment than the paper.
"""

import json
import math
from functools import lru_cache

import numpy as np

from app.config import PROCESSED_DIR
from ingestion.config import FIELDS as INGESTION_FIELDS

# Human-readable region per real field. These are the actual administrative
# locations of the localities named in ingestion/config.py (Sulur,
# Kinathukadavu and Annur are in Coimbatore district, Tamil Nadu; Ajnala is in
# Amritsar district, Punjab; Burdwan is in West Bengal; Amalapuram is in the
# East Godavari district of Andhra Pradesh) - display metadata for the same
# real polygons, not a second set of coordinates that could drift.
REGIONS = {
    "F001": "Coimbatore, TN",
    "F002": "Coimbatore, TN",
    "F003": "Coimbatore, TN",
    "F004": "Amritsar, PB",
    "F005": "Purba Bardhaman, WB",
    "F006": "East Godavari, AP",
    "F007": "Amritsar, PB",
}

CROP_DISPLAY = {
    "rice": "Rice",
    "rice_punjab": "Rice",
    "rice_west_bengal": "Rice",
    "rice_andhra_pradesh": "Rice",
    "wheat_punjab": "Wheat",
    "wheat": "Wheat",
    "maize": "Maize",
}

EARTH_RADIUS_M = 6_371_000.0


def _polygon_area_ha(ring: list[list[float]]) -> float:
    """Area of a small lon/lat ring, via the shoelace formula on an
    equirectangular projection about the ring's own mean latitude.

    Exact enough here by a wide margin: these polygons are ~2 km across, where
    the projection's distortion is far below the precision the number is
    displayed at. It is computed from the real geometry rather than stored as
    a literal so it can never disagree with the polygon actually sent to Earth
    Engine.
    """
    lats = [lat for _, lat in ring]
    lat0 = math.radians(sum(lats) / len(lats))
    pts = [
        (math.radians(lon) * EARTH_RADIUS_M * math.cos(lat0), math.radians(lat) * EARTH_RADIUS_M)
        for lon, lat in ring
    ]
    area_m2 = abs(
        sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))
    ) / 2.0
    return area_m2 / 10_000.0


def _build_fields() -> list[dict]:
    fields = []
    for f in INGESTION_FIELDS:
        fields.append(
            {
                "field_id": f["field_id"],
                "name": f["name"],
                "region": REGIONS.get(f["field_id"], "unknown"),
                "crop": CROP_DISPLAY.get(f["crop"], f["crop"]),
                "area_ha": round(_polygon_area_ha(f["geometry"][0]), 1),
            }
        )
    return fields


FIELDS = _build_fields()

_FIELD_INDEX = {f["field_id"]: f for f in FIELDS}


def list_fields() -> list[dict]:
    return FIELDS


def get_field(field_id: str) -> dict | None:
    return _FIELD_INDEX.get(field_id)


@lru_cache(maxsize=1)
def _all_real_examples() -> tuple:
    """Every real season example the training pipeline builds, cached.

    Returns an empty tuple rather than raising if the processed data or the
    yield labels are absent, so the API still starts on a checkout that has
    not run ingestion - the services then report that they have no real data
    for the field instead of inventing a curve.
    """
    try:
        from training.dataset import build_dataset_from_processed

        return tuple(build_dataset_from_processed())
    except (ImportError, FileNotFoundError, OSError):
        return ()


def latest_season_example(field_id: str):
    """The most recent real season for a field, as a SeasonExample carrying the
    aligned weekly satellite/weather/soil arrays the model consumes. None if
    the field has no processed real season."""
    seasons = [ex for ex in _all_real_examples() if ex.field_id == field_id]
    if not seasons:
        return None
    return max(seasons, key=lambda ex: ex.season_start_date or "")


def season_weeks(field_id: str) -> list[str] | None:
    """Real ISO week-start dates for the field's latest season, read back from
    the aligned table so the forecast curve is dated with the weeks the data
    actually covers rather than an offset from today's date."""
    ex = latest_season_example(field_id)
    if ex is None:
        return None
    path = PROCESSED_DIR / f"{field_id}_aligned.csv"
    if not path.exists():
        return None
    import pandas as pd

    aligned = pd.read_csv(path, parse_dates=["week"])
    start = pd.Timestamp(ex.season_start_date)
    weeks = aligned.loc[aligned["week"] >= start, "week"].head(len(ex.growth_stage))
    dates = [d.date().isoformat() for d in weeks]
    # Seasons are padded to a fixed length by training/dataset.py; extend the
    # date axis the same way so the two stay the same length.
    while len(dates) < len(ex.growth_stage):
        last = pd.Timestamp(dates[-1]) + pd.Timedelta(weeks=1) if dates else start
        dates.append(last.date().isoformat())
    return dates


def seeded_rng(field_id: str) -> np.random.Generator:
    """Deterministic per-field RNG. Retained only for endpoints that have no
    real data source yet and say so explicitly - it must never be used to
    manufacture a value that is then presented as a model output."""
    return np.random.default_rng(abs(hash(field_id)) % (2**32))


def load_json(path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        return None
