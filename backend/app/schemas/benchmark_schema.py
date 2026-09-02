from pydantic import BaseModel


class ClimateStressPoint(BaseModel):
    """One real held-out climate-shock season from the benchmark test set."""

    season: str  # e.g. "F005 2022"
    label: str  # ERA5-derived: "drought" | "wet_extreme" | "heatwave"
    actual_yield_t_ha: float


class LeaderboardEntry(BaseModel):
    """One model's real score on the shock test set.

    MAE in t/ha, not R^2: that is what
    evaluation/climate_shock_benchmark/run_climate_shock.py computes, and R^2
    over a handful of test seasons is not a meaningful summary. The sample
    sizes travel with every row so the number is never read without them.
    """

    model: str
    mae_shock_t_ha: float
    n_test_seasons: int
    n_train_seasons: int
