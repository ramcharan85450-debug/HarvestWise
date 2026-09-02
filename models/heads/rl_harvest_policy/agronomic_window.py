"""
Agronomically-grounded earliest harvest week.

The RL environment and the static optimizer both need a `min_harvest_week` -
the first week at which harvesting is agronomically valid. That bound was
`season_len // 2`, i.e. "halfway through whatever slice the segmenter
produced", which has no agronomic meaning and, worse, turned out to be
binding: measured over 21 real seasons, the trained policy chose week 10-12
almost every time, and week 10 IS `season_len // 2`. The policy was not
selecting a harvest week, it was returning the earliest week it was allowed to
return, and it disagreed with published agronomic guidance on 20 of 21 seasons
(evaluation/outcome_validation/agronomic_agreement.py).

This replaces that with IRRI's published optimum, anchored to the season's own
observed phenology:

    heading + 32-38 days   wet-season (kharif) harvest
    heading + 28-35 days   dry-season (rabi) harvest
    http://www.knowledgebank.irri.org/training/fact-sheets/item/when-to-harvest-fact-sheet

Heading is estimated as the week of peak NDVI - the standard remote-sensing
proxy, since canopy greenness peaks around heading/anthesis and declines
through grain fill. It is a proxy with roughly one-week error at this
resolution, which is stated wherever the resulting numbers are reported.

Note what this does and does not do. It constrains WHEN the policy may
harvest, using agronomy rather than an arbitrary fraction; it does not tell
the policy which week within that range is best, which is still learned from
the yield and rainfall trajectory. So the policy retains a real decision - it
is simply no longer able to make an agronomically impossible one.
"""

import numpy as np

DAYS_PER_STEP = 7

# (earliest, latest) days after heading, from the IRRI fact sheet above.
WET_SEASON_DAH = (32, 38)
DRY_SEASON_DAH = (28, 35)


def heading_week(vision_x: np.ndarray) -> int:
    """Week of peak NDVI (column 0 of vision_x) - the heading proxy."""
    return int(np.argmax(vision_x[:, 0]))


def window_for_crop(crop: str) -> tuple[int, int]:
    """Kharif rice is harvested coming out of the monsoon; Punjab rabi wheat
    matures into the dry season."""
    return DRY_SEASON_DAH if crop.startswith("wheat") else WET_SEASON_DAH


def agronomic_bounds(vision_x: np.ndarray, crop: str, season_len: int) -> tuple[int, int]:
    """Returns (min_harvest_week, max_harvest_week), clipped into the season.

    Falls back to the old season_len // 2 lower bound only if the agronomic
    window lies entirely outside the observed season - which happens when the
    NDVI peak sits near the end of the slice, i.e. when the season was not
    fully observed. Those seasons are better dropped than harvested by
    fallback, and build_rl_trajectories() below flags them.
    """
    lo_days, hi_days = window_for_crop(crop)
    head = heading_week(vision_x)
    lo = head + lo_days // DAYS_PER_STEP
    hi = head + int(np.ceil(hi_days / DAYS_PER_STEP))

    if lo >= season_len - 1:
        return season_len // 2, season_len - 1
    return int(lo), int(min(hi, season_len - 1))


def window_is_observed(vision_x: np.ndarray, crop: str, season_len: int) -> bool:
    """True when the agronomic harvest window actually falls inside the
    observed season, so a recommendation for it is meaningful."""
    lo_days, _ = window_for_crop(crop)
    return heading_week(vision_x) + lo_days // DAYS_PER_STEP < season_len - 1
