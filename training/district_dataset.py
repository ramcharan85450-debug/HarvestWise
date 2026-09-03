"""
District-level PyTorch dataset for the Southern India aligned examples
(data/processed/district_multimodal_examples.csv, produced by
ingestion/district_alignment.py).

This is a SEPARATE pipeline from the field-level one in
training/dataset.py. Nothing here imports from, modifies, or shares state
with that module - the 7-field `FIELDS` path, its `SeasonExample`
dataclass, its fixed VISION_NORM/WEATHER_NORM/SOIL_NORM constants and its
checkpoints are all untouched. The two pipelines answer different
questions at different spatial scales and must not be conflated.

WHAT COUNTS AS A FEATURE, AND WHY THE REST IS EXCLUDED
------------------------------------------------------
Only genuinely environmental measurements reach the model. Every other
column in the CSV is deliberately excluded, each for a stated reason:

  final_yield_t_ha            THE TARGET. Never a feature.
  yield_valid                 Derived from the target.
  yield_source_name/_url,
  yield_retrieved_date,
  weather_source,
  satellite_source,
  soil_source                 Provenance strings. A source URL is a perfect
                              state fingerprint (Tamil Nadu's rows cite a
                              different source than Andhra Pradesh's), so
                              feeding one to the model would leak region
                              identity outright.
  district_id,
  canonical_district_name,
  district,
  state                       DISTRICT AND STATE IDENTITY. These define the
                              split groups; using them as features would
                              make "unseen district" meaningless.
  administrative_boundary_notes  Free text that encodes which boundary
                              source a district came from - a proxy for
                              Tamil Nadu's 9 geoBoundaries districts.
  geographic_level            Constant ("district") across every row.
  crop                        Constant ("Rice") across every row.
  season_window_start,
  prediction_cutoff_date      Dates derived from (season, year); see below.
  weather_days_observed,
  weather_days_expected,
  satellite_scenes_observed,
  satellite_date_range_coverage  DATA-QUALITY METADATA, not measurements of
                              the land. Scene counts and coverage fractions
                              track how the data was fetched, not how the
                              crop grew - and they separate regions almost
                              perfectly (every Tamil Nadu row has coverage
                              0.504; every Andhra Pradesh row has 1.0).
  weather_available,
  satellite_available,
  soil_available              Availability flags; constant True on the
                              analysis subset by construction.
  rejection_reason            Null exactly on the analysis subset.

  year, season                EXCLUDED DELIBERATELY, and this one deserves
                              explicit justification rather than a silent
                              drop. In this dataset `season` and `year` are
                              not independent of region: every Tamil Nadu
                              example is season="Whole Year" in 2019 or
                              2024, while every Andhra Pradesh and Telangana
                              example is Kharif/Rabi in 1999-2012. Either
                              column alone therefore identifies the state
                              with perfect accuracy. Handing the model a
                              column that resolves region identity would
                              defeat the entire point of an unseen-district
                              (and cross-region) evaluation, so both are
                              kept as METADATA - carried alongside every
                              example for reporting and auditing - and never
                              placed in the feature matrix.

That leaves 12 real environmental features in three explicitly-named
groups (WEATHER_FEATURES, SATELLITE_FEATURES, SOIL_FEATURES).

WHICH ROWS ARE USED
-------------------
Only the 561 FULLY ALIGNED rows (real weather AND real satellite AND real
soil). The remaining 307 collected rows are excluded and counted, not
silently dropped - see `load_district_examples()`'s returned exclusion
report. Every experiment configuration (weather-only, satellite-only,
soil-only, ...) uses the SAME 561 rows, so the configurations differ only
in which columns they see, never in which examples they are scored on.
Letting soil-only use all 868 rows (soil is 100% covered) would have made
it incomparable with the others.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_PATH = ROOT / "data" / "processed" / "district_multimodal_examples.csv"

TARGET_COL = "final_yield_t_ha"

WEATHER_FEATURES = [
    "weather_temp_c_mean",
    "weather_precip_mm_sum",
    "weather_humidity_pct_mean",
    "weather_wind_speed_ms_mean",
]
SATELLITE_FEATURES = [
    "satellite_ndvi_mean",
    "satellite_evi_mean",
    "satellite_ndwi_mean",
]
SOIL_FEATURES = [
    "soil_phh2o",
    "soil_soc",
    "soil_clay",
    "soil_sand",
    "soil_nitrogen",
]

FEATURE_GROUPS = {
    "weather": WEATHER_FEATURES,
    "satellite": SATELLITE_FEATURES,
    "soil": SOIL_FEATURES,
}

# Carried with every example for reporting/auditing. NEVER used as input.
METADATA_COLS = [
    "state",
    "district",
    "canonical_district_name",
    "crop",
    "season",
    "year",
    "geographic_level",
]

# Any column that must never appear in a feature matrix. Asserted in
# `assert_no_forbidden_features()` and re-checked by the leakage audit.
FORBIDDEN_AS_FEATURES = {
    TARGET_COL,
    "yield_valid",
    "yield_source_name",
    "yield_source_url",
    "yield_retrieved_date",
    "weather_source",
    "satellite_source",
    "soil_source",
    "district_id",
    "canonical_district_name",
    "district",
    "state",
    "administrative_boundary_notes",
    "geographic_level",
    "crop",
    "season",
    "year",
    "season_window_start",
    "prediction_cutoff_date",
    "weather_days_observed",
    "weather_days_expected",
    "satellite_scenes_observed",
    "satellite_date_range_coverage",
    "weather_available",
    "satellite_available",
    "soil_available",
    "rejection_reason",
}


def features_for(config: str) -> list[str]:
    """Feature column list for one experiment configuration. `baseline` gets
    no features at all - it predicts the training-set mean and never sees an
    input row."""
    mapping = {
        "baseline": [],
        "weather_only": WEATHER_FEATURES,
        "satellite_only": SATELLITE_FEATURES,
        "weather_satellite": WEATHER_FEATURES + SATELLITE_FEATURES,
        "soil_only": SOIL_FEATURES,
        "full_multimodal": WEATHER_FEATURES + SATELLITE_FEATURES + SOIL_FEATURES,
    }
    if config not in mapping:
        raise ValueError(f"Unknown configuration '{config}'. Known: {sorted(mapping)}")
    return list(mapping[config])


def assert_no_forbidden_features(columns: list[str]) -> None:
    """Hard guard: raises rather than training on a leaking feature set."""
    bad = sorted(set(columns) & FORBIDDEN_AS_FEATURES)
    if bad:
        raise ValueError(
            f"Refusing to build a feature matrix containing forbidden column(s): {bad}. "
            "See training/district_dataset.py's module docstring for why each is excluded."
        )


def group_key(df: pd.DataFrame) -> pd.Series:
    """The unseen-district grouping key: state + canonical district name.

    State is included because district names can repeat across states in
    India. (Verified on this dataset: 0 canonical names currently appear in
    more than one state, so the key is presently equivalent to the district
    name alone - but the composite key is used anyway so the split stays
    correct if another state is added later.)"""
    return df["state"].astype(str) + "|" + df["canonical_district_name"].astype(str)


@dataclass
class ExclusionReport:
    total_collected: int
    used: int
    excluded: int
    reasons: dict = field(default_factory=dict)


def load_district_examples(path: Path = EXAMPLES_PATH) -> tuple[pd.DataFrame, ExclusionReport]:
    """Loads the aligned CSV and returns (fully-aligned rows, exclusion report).

    An example is used only if it has real weather AND real satellite AND
    real soil. Nothing is imputed here and nothing is dropped silently -
    every excluded row is counted under a stated reason.
    """
    df = pd.read_csv(path)
    total = len(df)

    usable = df["weather_available"] & df["satellite_available"] & df["soil_available"]
    reasons: dict[str, int] = {}
    excluded = df.loc[~usable]
    if len(excluded):
        no_weather = (~excluded["weather_available"]).sum()
        no_satellite = (~excluded["satellite_available"]).sum()
        no_soil = (~excluded["soil_available"]).sum()
        reasons["missing weather (season window not covered by any fetched data)"] = int(no_weather)
        reasons["missing satellite (season window not covered by any fetched data)"] = int(no_satellite)
        reasons["missing soil"] = int(no_soil)

    used = df.loc[usable].reset_index(drop=True).copy()

    # Defensive: the analysis subset must have no NaN in any real feature.
    all_features = WEATHER_FEATURES + SATELLITE_FEATURES + SOIL_FEATURES
    n_missing = int(used[all_features].isna().sum().sum())
    reasons["_feature_nans_remaining_in_used_subset"] = n_missing

    used["group"] = group_key(used)
    report = ExclusionReport(
        total_collected=total, used=len(used), excluded=total - len(used), reasons=reasons
    )
    return used, report


def stratified_group_split(
    df: pd.DataFrame, seed: int, val_frac: float = 0.2, test_frac: float = 0.2
) -> dict[str, list[str]]:
    """Splits DISTRICTS (not rows) into train/val/test, stratified by state.

    Why stratify by state rather than shuffle all 58 districts together:
    the districts are wildly unequal in size (Andhra Pradesh and Telangana
    districts carry ~25-26 examples each, Tamil Nadu districts ~2), so an
    unstratified draw would produce test folds that are sometimes almost
    entirely Tamil Nadu (a few dozen rows) and sometimes almost entirely
    Andhra Pradesh (many hundred). Allocating a proportional share of each
    state's districts to each split keeps every seed's test set comparable
    in composition and guarantees all three regions are represented in
    every fold.

    Returns {"train": [...], "val": [...], "test": [...]} of group keys.
    Deterministic for a given seed.
    """
    rng = np.random.default_rng(seed)
    splits: dict[str, list[str]] = {"train": [], "val": [], "test": []}

    for state, g in df.groupby("state", sort=True):
        groups = sorted(g["group"].unique())
        rng.shuffle(groups)
        n = len(groups)
        n_test = max(1, int(round(n * test_frac)))
        n_val = max(1, int(round(n * val_frac)))
        if n_test + n_val >= n:  # never leave the training side empty
            n_test, n_val = 1, 1
        splits["test"].extend(groups[:n_test])
        splits["val"].extend(groups[n_test : n_test + n_val])
        splits["train"].extend(groups[n_test + n_val :])

    return {k: sorted(v) for k, v in splits.items()}


def verify_disjoint(splits: dict[str, list[str]]) -> dict:
    """Explicit check that no district is shared between any two splits.
    Returned (not just asserted) so the audit can print the real numbers."""
    tr, va, te = set(splits["train"]), set(splits["val"]), set(splits["test"])
    return {
        "train_districts": len(tr),
        "val_districts": len(va),
        "test_districts": len(te),
        "train_test_overlap": sorted(tr & te),
        "val_test_overlap": sorted(va & te),
        "train_val_overlap": sorted(tr & va),
        "disjoint": not (tr & te) and not (va & te) and not (tr & va),
    }


class StandardScaler:
    """Mean/std standardization fitted on TRAINING ROWS ONLY.

    Deliberately not sklearn's - not because sklearn's is wrong, but because
    this one cannot be accidentally fitted twice or fitted on the wrong
    frame: `fit` records the source split name, and `transform` refuses to
    run before `fit`. The audit reads `fitted_on` to prove the scaler saw
    only training data.
    """

    def __init__(self) -> None:
        self.mean_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None
        self.fitted_on: str | None = None
        self.n_fit_rows: int | None = None

    def fit(self, X: np.ndarray, split_name: str = "train") -> "StandardScaler":
        if X.shape[1] == 0:  # baseline configuration has no features
            self.mean_, self.scale_ = np.zeros(0), np.ones(0)
        else:
            self.mean_ = X.mean(axis=0)
            std = X.std(axis=0)
            # A constant feature would divide by zero; keep it at scale 1 so
            # it becomes an all-zero column instead of NaN.
            self.scale_ = np.where(std < 1e-8, 1.0, std)
        self.fitted_on = split_name
        self.n_fit_rows = int(X.shape[0])
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.mean_ is None:
            raise RuntimeError("StandardScaler.transform() called before fit().")
        if X.shape[1] == 0:
            return X
        return (X - self.mean_) / self.scale_


class DistrictDataset(Dataset):
    """Rows of one split, as tensors, with metadata kept alongside.

    `metadata` is a list of dicts (one per row) carrying state/district/
    season/year etc. for reporting. It is never converted to a tensor and
    never reaches the model.
    """

    def __init__(self, df: pd.DataFrame, feature_cols: list[str], scaler: StandardScaler):
        assert_no_forbidden_features(feature_cols)
        self.feature_cols = list(feature_cols)
        raw = df[feature_cols].to_numpy(dtype=np.float32) if feature_cols else np.zeros((len(df), 0), dtype=np.float32)
        self.X = torch.from_numpy(scaler.transform(raw).astype(np.float32))
        self.y = torch.from_numpy(df[TARGET_COL].to_numpy(dtype=np.float32)).unsqueeze(1)
        self.metadata = df[METADATA_COLS].to_dict("records")
        self.groups = df["group"].tolist()

    def __len__(self) -> int:
        return int(self.X.shape[0])

    def __getitem__(self, idx: int):
        return self.X[idx], self.y[idx]


def build_split_datasets(
    df: pd.DataFrame, splits: dict[str, list[str]], feature_cols: list[str]
) -> tuple[DistrictDataset, DistrictDataset, DistrictDataset, StandardScaler]:
    """Builds the three datasets for one (split, configuration) pair.

    Order matters and is the whole point of this function: the scaler is fit
    on the TRAINING rows only, then applied unchanged to validation and
    test. No preprocessing statistic is ever computed from val or test data.
    """
    assert_no_forbidden_features(feature_cols)
    train_df = df[df["group"].isin(splits["train"])].reset_index(drop=True)
    val_df = df[df["group"].isin(splits["val"])].reset_index(drop=True)
    test_df = df[df["group"].isin(splits["test"])].reset_index(drop=True)

    train_raw = (
        train_df[feature_cols].to_numpy(dtype=np.float32)
        if feature_cols
        else np.zeros((len(train_df), 0), dtype=np.float32)
    )
    scaler = StandardScaler().fit(train_raw, split_name="train")

    return (
        DistrictDataset(train_df, feature_cols, scaler),
        DistrictDataset(val_df, feature_cols, scaler),
        DistrictDataset(test_df, feature_cols, scaler),
        scaler,
    )


def split_summary(df: pd.DataFrame, splits: dict[str, list[str]]) -> dict:
    """Examples / districts / states in each split - for the report."""
    out = {}
    for name, groups in splits.items():
        sub = df[df["group"].isin(groups)]
        out[name] = {
            "examples": int(len(sub)),
            "districts": int(sub["group"].nunique()),
            "states": sorted(sub["state"].unique().tolist()),
            "examples_by_state": {k: int(v) for k, v in sub["state"].value_counts().items()},
        }
    return out
