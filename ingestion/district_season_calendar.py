"""
Season-window and prediction-cutoff definitions for the district-level
alignment pipeline (ingestion/district_alignment.py).

TASK DEFINITION (Phase 7 requires choosing exactly one, explicitly, and not
mixing horizons): **pre-harvest forecasting**. For each (state, district,
crop, season, year) yield observation, environmental features are aggregated
from the season's sowing window through its harvest window (inclusive) -
never beyond it. `prediction_cutoff_date` = the season's own end date; no
weather or satellite observation dated after that cutoff is ever included in
that observation's features. This mirrors the existing field-level pipeline's
convention (training/dataset.py's SeasonExample: a fixed-length window from
planting through the crop calendar's season length, nothing beyond).

Windows follow the standard Government of India agricultural-year convention
used throughout this project's own sources (e.g. Tamil Nadu's "Season and
Crop Report 2024-25" title, data.gov.in's Crop_Year field): the agricultural
year for year Y runs July 1, Y - June 30, Y+1; Kharif is the monsoon-sown
portion of it; Rabi is the winter-sown portion, which crosses into calendar
year Y+1. These are STANDARD CALENDAR CONVENTIONS, not per-district verified
sowing/harvest dates - the same honesty standard already applied to
ingestion/config.py's CROP_CALENDARS (see e.g. its "rice_punjab" entry:
"general agronomic knowledge, not a cited government calendar document").
A source that publishes its own exact sowing/harvest dates for a specific
season should be preferred over these generic windows if one is ever found.
"""

from datetime import date


def season_window(season: str, year: int) -> tuple[date, date]:
    """Returns (window_start, prediction_cutoff_date) for one (season, year)
    yield observation. `year` is the source's own Crop_Year / reporting year,
    exactly as it appears in the *_apy_clean.csv files - not reinterpreted."""
    season_norm = season.strip().lower()
    year = int(year)

    if season_norm == "kharif":
        return date(year, 6, 1), date(year, 11, 30)
    if season_norm == "rabi":
        # Crosses into the following calendar year - deliberately, not a bug.
        return date(year, 11, 1), date(year + 1, 4, 30)
    if season_norm in ("whole year", "wholeyear"):
        return date(year, 7, 1), date(year + 1, 6, 30)

    raise ValueError(f"Unrecognized season '{season}' - add an explicit window rather than guessing one.")


def years_touched(season: str, year: int) -> list[int]:
    """Which calendar years' raw weather/satellite files must be read to
    cover this season's window - Rabi and Whole Year touch two calendar
    years; Kharif touches one."""
    start, end = season_window(season, year)
    return sorted({start.year, end.year})
