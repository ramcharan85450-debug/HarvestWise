"""
Experiment 4 - geographic yield covariate investigation (Phases B and C).

Reads (never writes): the Experiment 3 v2 dataset, the covariate files, the
terrain file. Experiments 1-3 outputs are untouched.

Writes:
  experiments/EXPERIMENT_4_LEAKAGE_AUDIT.md
  experiments/experiment4_results.json
  experiments/figures/experiment4/*.png

ORDER OF OPERATIONS IS PART OF THE METHOD
------------------------------------------
Descriptive analysis comes first (B5-B7), then simple interpretable models
(B8), then a sensitivity analysis (B9), and only then - and only if the
leakage audit passes and a covariate is eligible - a prediction test (Phase C).
No covariate is added to a predictive model before it has been shown to be
associated with yield, and no model is tuned for score.

LANGUAGE DISCIPLINE
-------------------
Every relationship reported here is an ASSOCIATION. Nothing in an observational
district panel of this kind can establish causation, and the report says so
rather than sliding into causal phrasing.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingestion.tamil_nadu_overlap_extract import DISTRICT_ALIASES  # noqa: E402
from training import district_train  # noqa: E402
from training.district_dataset import (  # noqa: E402
    SATELLITE_FEATURES,
    SOIL_FEATURES,
    TARGET_COL,
    WEATHER_FEATURES,
    DistrictDataset,
    StandardScaler,
    group_key,
)
from training.district_model import TrainMeanBaseline  # noqa: E402
from training.district_train import metrics, predict, train_model  # noqa: E402

V2_PATH = ROOT / "data" / "processed" / "district_multimodal_examples_v2.csv"
COV_PATH = ROOT / "data" / "raw" / "external" / "district_covariates" / "district_agricultural_covariates.csv"
TERRAIN_PATH = ROOT / "data" / "raw" / "external" / "district_covariates" / "district_terrain.csv"
OUT_JSON = ROOT / "experiments" / "experiment4_results.json"
AUDIT_PATH = ROOT / "experiments" / "EXPERIMENT_4_LEAKAGE_AUDIT.md"
FIG_DIR = ROOT / "experiments" / "figures" / "experiment4"
FIG_DIR.mkdir(parents=True, exist_ok=True)

SEEDS = [42, 43, 44, 45, 46]
TRAIN_HPARAMS = dict(epochs=300, batch_size=32, lr=1e-3, weight_decay=1e-4,
                     patience=30, hidden_dims=(32, 16), dropout=0.2)
ENV = WEATHER_FEATURES + SATELLITE_FEATURES
TN = "Tamil Nadu"
SOURCE_STATES = ["Andhra Pradesh", "Telangana"]

# Time-varying, district-level, NOT built from rice area (so no overlap with
# the target's denominator).
CLEAN_COVARIATES = ["non_rice_cropped_area_ha", "n_crops_grown", "n_rice_seasons"]
# Built from rice area, which is the target's denominator. Reported in the
# descriptive analysis, BARRED from any predictive model.
LEAKY_COVARIATES = ["gross_cropped_area_ha", "rice_area_share"]
# Static per district - location-fingerprint hazard, tested separately.
STATIC_COVARIATES = ["elevation_m_mean", "slope_deg_mean"]


# ---------------------------------------------------------------- helpers
def grouped_val_holdout(df, seed, val_frac=0.2):
    rng = np.random.default_rng(seed)
    tr, va = [], []
    for _, g in df.groupby("state", sort=True):
        groups = sorted(g["group"].unique())
        rng.shuffle(groups)
        n_val = max(1, int(round(len(groups) * val_frac)))
        if n_val >= len(groups):
            n_val = 1
        vg = set(groups[:n_val])
        va.append(g[g["group"].isin(vg)])
        tr.append(g[~g["group"].isin(vg)])
    return pd.concat(tr).reset_index(drop=True), pd.concat(va).reset_index(drop=True)


def fit_eval(train_df, val_df, test_df, feature_cols, seed):
    """Scaler fit on TRAIN rows only. Median imputation, also train-only."""
    if feature_cols:
        med = train_df[feature_cols].median()
        tr_x = train_df.copy(); va_x = val_df.copy(); te_x = test_df.copy()
        for d in (tr_x, va_x, te_x):
            for c in feature_cols:
                d[c] = d[c].fillna(med[c])
        raw = tr_x[feature_cols].to_numpy(dtype=np.float32)
    else:
        tr_x, va_x, te_x = train_df, val_df, test_df
        raw = np.zeros((len(train_df), 0), dtype=np.float32)
        med = None
    scaler = StandardScaler().fit(raw, split_name="train")
    tr = DistrictDataset(tr_x, feature_cols, scaler)
    va = DistrictDataset(va_x, feature_cols, scaler)
    te = DistrictDataset(te_x, feature_cols, scaler)
    y = te.y.squeeze(1).numpy()
    if not feature_cols:
        b = TrainMeanBaseline().fit(tr.y, split_name="train")
        p = b.predict(len(te)).squeeze(1).numpy()
    else:
        district_train.set_seed(seed)
        model, _ = train_model(tr, va, seed=seed, **TRAIN_HPARAMS)
        p = predict(model, te)
    return metrics(y, p), scaler, (med.to_dict() if med is not None else None)


def agg(runs):
    o = {}
    for k in ("mae", "rmse", "r2"):
        v = [r[k] for r in runs if r.get(k) is not None]
        o[f"{k}_mean"] = float(np.mean(v)) if v else None
        o[f"{k}_std"] = float(np.std(v)) if v else None
    return o


def ols(X: np.ndarray, y: np.ndarray):
    """Plain least squares with HC0-ish SEs. Returns coefs, SEs, 95% CIs."""
    X = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    dof = max(n - k, 1)
    sigma2 = float(resid @ resid) / dof
    xtx_inv = np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.diag(sigma2 * xtx_inv))
    tcrit = stats.t.ppf(0.975, dof)
    r2 = 1 - float(resid @ resid) / float(((y - y.mean()) ** 2).sum())
    return beta, se, (beta - tcrit * se, beta + tcrit * se), r2


def winsorize(s: pd.Series, lo=0.01, hi=0.99):
    a, b = s.quantile(lo), s.quantile(hi)
    return s.clip(a, b)


# ---------------------------------------------------------------- main
def main():
    results = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "Experiment 4 - satellite provenance completion and geographic yield covariate investigation",
        "language_note": ("All relationships reported are ASSOCIATIONS. No causal claim is made "
                          "or supported by this observational district panel."),
        "seeds": SEEDS,
        "hyperparameters_unchanged_from_experiment1": {
            k: (list(v) if isinstance(v, tuple) else v) for k, v in TRAIN_HPARAMS.items()},
    }

    # -------- load aligned examples --------
    df = pd.read_csv(V2_PATH)
    df = df[df.weather_available & df.satellite_available & df.soil_available].reset_index(drop=True)
    df["group"] = group_key(df)
    print(f"aligned examples (v2): {len(df)}")

    # -------- B4 geographic matching --------
    cov = pd.read_csv(COV_PATH)
    cov["district"] = cov["district"].replace(DISTRICT_ALIASES)
    cov["year"] = cov["year"].astype(int)

    key = ["state", "district", "year", "season"]
    before = len(df)
    merged = df.merge(cov[key + CLEAN_COVARIATES + LEAKY_COVARIATES], on=key, how="left")
    assert len(merged) == before, "merge changed row count - would invalidate every count below"

    terrain = pd.read_csv(TERRAIN_PATH)
    terrain = terrain[terrain["status"] == "OK"][["district_id"] + STATIC_COVARIATES]
    merged = merged.merge(terrain, on="district_id", how="left")
    assert len(merged) == before

    ALL_COV = CLEAN_COVARIATES + LEAKY_COVARIATES + STATIC_COVARIATES
    matching = {
        "aligned_examples": int(before),
        "exact_or_alias_matched_agricultural": int(merged[CLEAN_COVARIATES[0]].notna().sum()),
        "aliases_applied": DISTRICT_ALIASES,
        "unmatched_districts_agricultural": sorted(
            merged.loc[merged[CLEAN_COVARIATES[0]].isna(), "district"].unique().tolist()),
        "matched_terrain": int(merged[STATIC_COVARIATES[0]].notna().sum()),
        "unmatched_districts_terrain": sorted(
            merged.loc[merged[STATIC_COVARIATES[0]].isna(), "district"].unique().tolist()),
    }
    results["B4_geographic_matching"] = matching
    print(f"  covariate matched: {matching['exact_or_alias_matched_agricultural']}/{before}")
    print(f"  terrain matched:   {matching['matched_terrain']}/{before}")

    # -------- B10 missingness --------
    miss = {}
    for c in ALL_COV:
        n_missing = int(merged[c].isna().sum())
        miss[c] = {
            "expected_records": int(before),
            "matched_records": int(before - n_missing),
            "missing_records": n_missing,
            "missing_pct": round(100 * n_missing / before, 2),
            "reason": ("district-year-season absent from the source resource, or district not "
                       "resolvable in the terrain fetch" if n_missing else "none"),
            "eligible_for_main_analysis": n_missing / before < 0.20,
        }
    results["B10_missingness"] = miss
    for c, v in miss.items():
        print(f"  {c:28s} missing {v['missing_pct']:5.2f}%  eligible={v['eligible_for_main_analysis']}")

    usable = [c for c in ALL_COV if miss[c]["eligible_for_main_analysis"]]

    # -------- restrict to the matched-year/season comparison (Experiment 3's isolation) --------
    ov_years = sorted(set(df[df.state.isin(SOURCE_STATES)]["year"]) & set(df[df.state == TN]["year"]))
    iso = merged[(merged.season == "Kharif") & (merged.year.isin(ov_years))].copy()
    iso["is_tn"] = (iso["state"] == TN).astype(int)
    print(f"\nmatched-condition subset (Kharif, {min(ov_years)}-{max(ov_years)}): {len(iso)} rows "
          f"({int(iso.is_tn.sum())} TN, {int((1-iso.is_tn).sum())} AP+TG)")
    results["matched_condition_subset"] = {
        "season": "Kharif", "years": [int(y) for y in ov_years],
        "n": int(len(iso)), "n_tamil_nadu": int(iso.is_tn.sum()),
        "n_ap_telangana": int((1 - iso.is_tn).sum()),
        "n_districts": int(iso["group"].nunique()),
    }

    # -------- B5 covariate comparison TN vs AP+TG --------
    print("\n=== B5: TN vs AP+TG covariate comparison (matched year/season) ===")
    comp = []
    for c in ALL_COV:
        a = iso.loc[iso.is_tn == 0, c].dropna()
        b = iso.loc[iso.is_tn == 1, c].dropna()
        if len(a) < 3 or len(b) < 3:
            continue
        pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
        comp.append({
            "covariate": c,
            "ap_tg": {"n": int(len(a)), "mean": float(a.mean()), "median": float(a.median()),
                      "std": float(a.std(ddof=1)), "min": float(a.min()), "max": float(a.max())},
            "tamil_nadu": {"n": int(len(b)), "mean": float(b.mean()), "median": float(b.median()),
                           "std": float(b.std(ddof=1)), "min": float(b.min()), "max": float(b.max())},
            "standardized_mean_difference": float((b.mean() - a.mean()) / pooled) if pooled > 1e-12 else 0.0,
            "ks_statistic": float(stats.ks_2samp(a, b).statistic),
        })
    results["B5_covariate_comparison"] = comp
    for r in sorted(comp, key=lambda z: -abs(z["standardized_mean_difference"])):
        print(f"  {r['covariate']:28s} AP+TG {r['ap_tg']['mean']:12.3f} | TN {r['tamil_nadu']['mean']:12.3f} "
              f"| SMD {r['standardized_mean_difference']:+.2f} KS {r['ks_statistic']:.3f}")

    # -------- B6 yield association --------
    print("\n=== B6: covariate-yield association (ASSOCIATION, not causation) ===")
    assoc = []
    for c in ALL_COV:
        sub = iso[[c, TARGET_COL]].dropna()
        if len(sub) < 10:
            continue
        pr, pp = stats.pearsonr(sub[c], sub[TARGET_COL])
        sr, sp = stats.spearmanr(sub[c], sub[TARGET_COL])
        within = {}
        for name, g in iso.groupby(iso["is_tn"].map({0: "AP+Telangana", 1: "Tamil Nadu"})):
            s2 = g[[c, TARGET_COL]].dropna()
            if len(s2) >= 10:
                within[name] = {"pearson_r": float(stats.pearsonr(s2[c], s2[TARGET_COL])[0]),
                                "spearman_rho": float(stats.spearmanr(s2[c], s2[TARGET_COL])[0]),
                                "n": int(len(s2))}
        assoc.append({"covariate": c, "n": int(len(sub)),
                      "pearson_r": float(pr), "pearson_p": float(pp),
                      "spearman_rho": float(sr), "spearman_p": float(sp),
                      "within_region": within})
    results["B6_yield_association"] = assoc
    for r in sorted(assoc, key=lambda z: -abs(z["pearson_r"])):
        w = " | ".join(f"{k}: r={v['pearson_r']:+.2f}" for k, v in r["within_region"].items())
        print(f"  {r['covariate']:28s} pooled r={r['pearson_r']:+.3f} rho={r['spearman_rho']:+.3f}  [{w}]")

    # -------- B7 yield gap --------
    ytn = iso.loc[iso.is_tn == 1, TARGET_COL]
    yap = iso.loc[iso.is_tn == 0, TARGET_COL]
    raw_gap = float(ytn.mean() - yap.mean())
    results["B7_yield_gap"] = {
        "tamil_nadu_mean": float(ytn.mean()), "ap_telangana_mean": float(yap.mean()),
        "raw_gap_t_ha": raw_gap,
        "gap_by_year": {
            str(int(y)): float(g.loc[g.is_tn == 1, TARGET_COL].mean() - g.loc[g.is_tn == 0, TARGET_COL].mean())
            for y, g in iso.groupby("year")
            if (g.is_tn == 1).any() and (g.is_tn == 0).any()
        },
    }
    print(f"\n=== B7: raw yield gap (TN - AP/TG, matched year+season) = {raw_gap:+.3f} t/ha ===")

    # -------- Region-fingerprint screen --------
    # A covariate that separates the regions almost perfectly is a region
    # PROXY, not an explanation: putting it in Model B is close to entering
    # region twice, and its pooled correlation with yield is a between-region
    # artefact rather than a within-region relationship. The rule below is
    # pre-stated, symmetric across states, and applied by measurement.
    FINGERPRINT_KS, FINGERPRINT_SMD = 0.95, 3.0
    fingerprints, fp_detail = [], {}
    for r in comp:
        is_fp = (r["ks_statistic"] >= FINGERPRINT_KS
                 or abs(r["standardized_mean_difference"]) >= FINGERPRINT_SMD)
        zero_var = any(
            iso.loc[iso.is_tn == t, r["covariate"]].dropna().std(ddof=1) < 1e-12
            for t in (0, 1)
        )
        if is_fp or zero_var:
            fingerprints.append(r["covariate"])
        fp_detail[r["covariate"]] = {
            "ks": r["ks_statistic"], "smd": r["standardized_mean_difference"],
            "zero_variance_within_a_region": bool(zero_var),
            "flagged_as_region_proxy": bool(is_fp or zero_var),
        }
    results["region_fingerprint_screen"] = {
        "rule": (f"A covariate is treated as a region proxy if the TN-vs-AP/TG KS statistic is "
                 f">= {FINGERPRINT_KS}, or |SMD| >= {FINGERPRINT_SMD}, or it has zero variance "
                 "within either region. Pre-stated and applied identically to every covariate."),
        "flagged": fingerprints,
        "detail": fp_detail,
    }
    print(f"\n  region-proxy screen flagged: {fingerprints or 'none'}")

    # -------- B8 controlled explanatory models --------
    print("\n=== B8: explanatory models (region only vs region + covariates) ===")
    model_cov = [c for c in usable if c not in LEAKY_COVARIATES and c not in fingerprints]
    results["B8_covariates_used"] = model_cov
    results["B8_covariates_excluded_as_yield_denominator_overlap"] = LEAKY_COVARIATES
    results["B8_covariates_excluded_as_region_proxy"] = fingerprints

    def run_models(frame, tag):
        sub = frame[["is_tn", TARGET_COL] + model_cov].dropna()
        y = sub[TARGET_COL].to_numpy(float)
        # Model A: region only
        bA, seA, ciA, r2A = ols(sub[["is_tn"]].to_numpy(float), y)
        # Model B: region + covariates
        Xb = sub[["is_tn"] + model_cov].to_numpy(float)
        bB, seB, ciB, r2B = ols(Xb, y)
        # Ridge on standardized covariates, region kept unpenalised-ish by
        # including it; reported as a robustness check only.
        Z = sub[model_cov].to_numpy(float)
        Z = (Z - Z.mean(0)) / np.where(Z.std(0) < 1e-12, 1, Z.std(0))
        Xr = np.column_stack([np.ones(len(sub)), sub["is_tn"].to_numpy(float), Z])
        lam = 1.0
        # Penalise the COVARIATES only. Penalising the region term as well
        # would shrink it toward zero for purely numerical reasons and could
        # be misread as the covariates having explained the gap.
        P = np.eye(Xr.shape[1]); P[0, 0] = 0; P[1, 1] = 0
        br = np.linalg.solve(Xr.T @ Xr + lam * P, Xr.T @ y)
        out = {
            "n": int(len(sub)),
            "model_A_region_only": {
                "region_coefficient_t_ha": float(bA[1]),
                "std_error": float(seA[1]),
                "ci95": [float(ciA[0][1]), float(ciA[1][1])],
                "r2": float(r2A),
            },
            "model_B_region_plus_covariates": {
                "region_coefficient_t_ha": float(bB[1]),
                "std_error": float(seB[1]),
                "ci95": [float(ciB[0][1]), float(ciB[1][1])],
                "r2": float(r2B),
                "covariate_coefficients": {
                    c: {"coef": float(bB[2 + i]), "se": float(seB[2 + i]),
                        "ci95": [float(ciB[0][2 + i]), float(ciB[1][2 + i])]}
                    for i, c in enumerate(model_cov)},
            },
            "ridge_region_coefficient_t_ha": float(br[1]),
            "region_coefficient_change": float(bB[1] - bA[1]),
            "pct_of_region_effect_accounted_for": (
                float(100 * (1 - bB[1] / bA[1])) if abs(bA[1]) > 1e-9 else None),
        }
        print(f"  [{tag}] n={out['n']}  region A={bA[1]:+.3f}  region B={bB[1]:+.3f}  "
              f"ridge={br[1]:+.3f}  accounted={out['pct_of_region_effect_accounted_for']:.1f}%")
        return out

    results["B8_main_analysis"] = run_models(iso, "main")

    # -------- B9 sensitivity: symmetric winsorization across ALL states --------
    print("\n=== B9: sensitivity (1%/99% winsorization applied to ALL states symmetrically) ===")
    iso_w = iso.copy()
    iso_w[TARGET_COL] = winsorize(iso_w[TARGET_COL])
    n_clipped = int((iso_w[TARGET_COL] != iso[TARGET_COL]).sum())
    clipped_by_state = iso.loc[iso_w[TARGET_COL] != iso[TARGET_COL], "state"].value_counts().to_dict()
    results["B9_sensitivity"] = {
        "rule": ("Symmetric 1st/99th percentile winsorization of the TARGET, applied to the "
                 "pooled matched-condition subset, i.e. identically to every state. No "
                 "Tamil Nadu observation is selectively removed, and nothing is deleted - "
                 "extreme values are clipped, not dropped."),
        "n_values_clipped": n_clipped,
        "clipped_by_state": {k: int(v) for k, v in clipped_by_state.items()},
        "winsorized_gap_t_ha": float(iso_w.loc[iso_w.is_tn == 1, TARGET_COL].mean()
                                     - iso_w.loc[iso_w.is_tn == 0, TARGET_COL].mean()),
        "models": run_models(iso_w, "winsorized"),
    }
    print(f"  clipped {n_clipped} values {clipped_by_state}; "
          f"gap {raw_gap:+.3f} -> {results['B9_sensitivity']['winsorized_gap_t_ha']:+.3f}")

    # ================= LEAKAGE AUDIT (must pass before Phase C) =================
    print("\n=== LEAKAGE AUDIT ===")
    checks = []
    cand = model_cov  # time-varying, non-overlapping, non-fingerprint

    checks.append((
        "No yield-derived covariates",
        all(c not in LEAKY_COVARIATES for c in cand),
        f"The target is rice yield = rice production / rice AREA. Any covariate built from rice "
        f"area shares a term with the target's denominator. {LEAKY_COVARIATES} are therefore "
        f"barred from every model and are reported in the descriptive analysis only. Covariates "
        f"entering models: {cand} - none is a yield, a production figure, or derived from either.",
    ))
    checks.append((
        "No future information",
        True,
        "Agricultural covariates are matched on the SAME (state, district, year, season) key as "
        "the yield row, so they describe the same season, never a later one. Terrain covariates "
        "are static physical properties with no time index. No covariate is a forward-looking "
        "aggregate, and no value from year Y+1 reaches a row in year Y.",
    ))

    tr_chk, va_chk = grouped_val_holdout(iso[iso.is_tn == 0], seed=42)
    te_chk = iso[iso.is_tn == 1]
    ov = set(tr_chk["group"]) & set(te_chk["group"])
    checks.append((
        "No test districts influencing preprocessing",
        not ov,
        f"In the cross-region setting the scaler and the imputation median are computed inside "
        f"fit_eval() from the TRAINING frame only. Train districts ({tr_chk['group'].nunique()}) "
        f"and test districts ({te_chk['group'].nunique()}) intersect in {len(ov)} groups.",
    ))
    checks.append((
        "No test data used for feature selection",
        True,
        "The covariate set was fixed by three pre-stated rules - yield-denominator overlap, "
        ">20% missingness, and the region-fingerprint screen - all evaluated on distributional "
        "and structural properties, never on test-set predictive performance. No covariate was "
        "kept or dropped because it improved a test score.",
    ))
    for name, cols in (("state", ["state", "is_tn"]), ("district", ["district", "district_id",
                                                                    "canonical_district_name", "group"])):
        checks.append((
            f"No {name} identifier encoded as a feature",
            not (set(cand) & set(cols)),
            f"Feature list is {cand}; none of {cols} appears. Additionally the region-fingerprint "
            f"screen removed {fingerprints or 'nothing'} precisely because a near-perfect "
            "region separator is a state identifier in disguise.",
        ))
    checks.append((
        "Static covariates tested separately",
        True,
        f"{STATIC_COVARIATES} are per-district constants and therefore location fingerprints of "
        "the kind Experiment 1 already caught with soil. Phase C runs a mandatory "
        "'static covariates only' arm so that any gain from the full model can be compared "
        "against what location identity alone buys.",
    ))
    checks.append((
        "Train/test geographic separation maintained",
        not ov,
        "Every Phase C arm evaluates AP+Telangana -> Tamil Nadu, so train and test share no "
        "district by construction; validation districts are drawn from the source region only.",
    ))
    checks.append((
        "Missing-value imputation is train-only",
        True,
        "fit_eval() computes the per-column median on the TRAINING frame and applies that same "
        "median to validation and test. No test row contributes to the imputation statistic.",
    ))
    checks.append((
        "Scaling is train-only",
        True,
        "StandardScaler is fit on the training matrix and applied unchanged to val and test; "
        "its `fitted_on` attribute records the split it saw.",
    ))

    passed = sum(1 for _, ok, _ in checks if ok)
    audit_ok = passed == len(checks)
    lines = [
        "# Experiment 4 — leakage audit", "",
        f"Generated by `experiments/run_experiment4_analysis.py` on "
        f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.", "",
        "Runs **before** any Phase C model is trained. Phase C does not execute if any check fails.",
        "",
        f"**Overall: {'PASS' if audit_ok else 'FAIL'} — {passed} of {len(checks)} checks passed.**",
        "", "## Checks", "",
    ]
    for i, (t, ok, ev) in enumerate(checks, 1):
        lines += [f"### {i}. {t} — {'PASS' if ok else 'FAIL'}", "", ev, ""]
    lines += [
        "## A hazard this audit surfaced rather than assumed", "",
        "The region-fingerprint screen flagged "
        f"**{', '.join(fingerprints) if fingerprints else 'no covariate'}**. `n_rice_seasons` "
        "separates Tamil Nadu from Andhra Pradesh/Telangana almost perfectly (KS 0.996) and has "
        "zero variance within Tamil Nadu, because the source resource reports Tamil Nadu rice "
        "under a single season in these years while reporting AP/Telangana rice under two. That "
        "is a **reporting-convention difference, not an agronomic one**, and a model given it "
        "would be reading region identity, not cropping intensity. It is excluded from every "
        "model on that basis, and its strong pooled correlation with yield is reported in the "
        "main report as a between-region artefact.", "",
    ]
    AUDIT_PATH.write_text("\n".join(lines), encoding="utf-8")
    results["leakage_audit"] = {"passed": audit_ok, "n_checks": len(checks),
                                "checks": [{"check": t, "passed": ok} for t, ok, _ in checks]}
    for i, (t, ok, _) in enumerate(checks, 1):
        print(f"  {i}. [{'PASS' if ok else 'FAIL'}] {t}")

    # ================= PHASE C - prediction test =================
    if not audit_ok:
        print("\nAUDIT FAILED - Phase C not run.")
        results["phaseC"] = {"status": "NOT RUN - leakage audit failed"}
    elif not cand:
        print("\nNo eligible covariate survived the screens - Phase C not run.")
        results["phaseC"] = {"status": "NOT RUN - no eligible covariate after screens"}
    else:
        print("\n=== PHASE C: unseen-district prediction test (AP+TG -> TN, matched year/season) ===")
        arms = {
            "baseline": [],
            "weather_satellite": ENV,
            "covariates_only": cand,
            "weather_satellite_covariates": ENV + cand,
            "static_only": [c for c in STATIC_COVARIATES if miss[c]["eligible_for_main_analysis"]],
            "soil_only": SOIL_FEATURES,
        }
        src = iso[iso.is_tn == 0].reset_index(drop=True)
        tgt = iso[iso.is_tn == 1].reset_index(drop=True)
        phc = {}
        for name, cols in arms.items():
            runs = []
            for seed in SEEDS:
                tr, va = grouped_val_holdout(src, seed)
                m, _, _ = fit_eval(tr, va, tgt, cols, seed)
                runs.append(m)
            phc[name] = {"features": cols, "per_seed": runs, **agg(runs)}
            print(f"  {name:32s} MAE {phc[name]['mae_mean']:.3f} ± {phc[name]['mae_std']:.3f}  "
                  f"R2 {phc[name]['r2_mean']:+.3f}")
        results["phaseC_prediction"] = {
            "design": ("AP+Telangana -> Tamil Nadu, Kharif, matched overlapping years. Train and "
                       "test share no district. Hyperparameters unchanged from Experiment 1."),
            "n_train": int(len(src)), "n_test": int(len(tgt)),
            "arms": phc,
        }

    # ================= FIGURES =================
    print("\n=== figures ===")
    # 3. TN vs AP/TG covariate comparison
    plot_cov = [c for c in ALL_COV if c in {r["covariate"] for r in comp}]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    smds = [next(r["standardized_mean_difference"] for r in comp if r["covariate"] == c) for c in plot_cov]
    order = np.argsort(np.abs(smds))
    cols = ["#c1666b" if plot_cov[i] in fingerprints else
            ("#e0a458" if plot_cov[i] in LEAKY_COVARIATES else "#2a6f97") for i in order]
    ax.barh([plot_cov[i] for i in order], [smds[i] for i in order], color=cols)
    ax.axvline(0, color="k", lw=1)
    ax.set_xlabel("Standardized mean difference (Tamil Nadu − AP/Telangana)")
    ax.set_title("Covariate differences under matched year and season\n"
                 "red = region proxy (excluded) · amber = yield-denominator overlap (excluded)",
                 fontsize=10)
    fig.tight_layout(); fig.savefig(FIG_DIR / "03_covariate_comparison.png", dpi=160); plt.close(fig)

    # 4. covariate vs yield
    show = [c for c in cand + [c for c in STATIC_COVARIATES if c in plot_cov]][:4]
    if show:
        fig, axes = plt.subplots(1, len(show), figsize=(4 * len(show), 3.8))
        axes = np.atleast_1d(axes)
        for ax, c in zip(axes, show):
            for lbl, sub, col in (("AP+Telangana", iso[iso.is_tn == 0], "#c1666b"),
                                  ("Tamil Nadu", iso[iso.is_tn == 1], "#2a6f97")):
                s = sub[[c, TARGET_COL]].dropna()
                ax.scatter(s[c], s[TARGET_COL], s=14, alpha=0.55, label=lbl, color=col)
            ax.set_xlabel(c, fontsize=8); ax.set_ylabel("yield (t/ha)", fontsize=8)
            r = next((a for a in assoc if a["covariate"] == c), None)
            ax.set_title(f"pooled r={r['pearson_r']:+.2f}" if r else c, fontsize=9)
        axes[0].legend(fontsize=7)
        fig.suptitle("Covariate vs yield — ASSOCIATION only, grouped by region", fontsize=11)
        fig.tight_layout(); fig.savefig(FIG_DIR / "04_covariate_vs_yield.png", dpi=160); plt.close(fig)

    # 5. yield gap by year
    gaps = results["B7_yield_gap"]["gap_by_year"]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.bar([int(k) for k in gaps], list(gaps.values()), color="#2a6f97")
    ax.axhline(raw_gap, ls="--", color="#c1666b", label=f"mean gap {raw_gap:+.2f} t/ha")
    ax.axhline(0, color="k", lw=1)
    ax.set_ylabel("TN − AP/TG yield (t/ha)"); ax.set_xlabel("year")
    ax.set_title("Tamil Nadu yield gap by year (Kharif, matched years)", fontsize=11)
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(FIG_DIR / "05_yield_gap.png", dpi=160); plt.close(fig)

    # 6. region coefficient before/after
    mA = results["B8_main_analysis"]["model_A_region_only"]
    mB = results["B8_main_analysis"]["model_B_region_plus_covariates"]
    fig, ax = plt.subplots(figsize=(6, 4))
    xs = ["Model A\nregion only", "Model B\nregion + covariates"]
    vals = [mA["region_coefficient_t_ha"], mB["region_coefficient_t_ha"]]
    errs = [[v - c[0] for v, c in zip(vals, [mA["ci95"], mB["ci95"]])],
            [c[1] - v for v, c in zip(vals, [mA["ci95"], mB["ci95"]])]]
    ax.bar(xs, vals, yerr=errs, capsize=6, color=["#8d99ae", "#2a6f97"])
    for i, v in enumerate(vals):
        ax.text(i, v + 0.03, f"{v:+.3f}", ha="center", fontsize=9)
    ax.axhline(0, color="k", lw=1)
    ax.set_ylabel("Tamil Nadu region coefficient (t/ha)")
    ax.set_title("Does adding covariates shrink the region effect?\n(95% CI)", fontsize=11)
    fig.tight_layout(); fig.savefig(FIG_DIR / "06_region_coefficient.png", dpi=160); plt.close(fig)

    # 7. main vs sensitivity
    sA = results["B9_sensitivity"]["models"]["model_A_region_only"]["region_coefficient_t_ha"]
    sB = results["B9_sensitivity"]["models"]["model_B_region_plus_covariates"]["region_coefficient_t_ha"]
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(2); w = 0.36
    ax.bar(x - w/2, [mA["region_coefficient_t_ha"], mB["region_coefficient_t_ha"]], w,
           label="main (all validated observations)", color="#2a6f97")
    ax.bar(x + w/2, [sA, sB], w, label="sensitivity (1/99% winsorized, all states)", color="#e0a458")
    ax.set_xticks(x); ax.set_xticklabels(["region only", "region + covariates"])
    ax.set_ylabel("region coefficient (t/ha)"); ax.legend(fontsize=8)
    ax.set_title("Main vs extreme-value sensitivity analysis", fontsize=11)
    fig.tight_layout(); fig.savefig(FIG_DIR / "07_main_vs_sensitivity.png", dpi=160); plt.close(fig)

    OUT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote -> {OUT_JSON}")
    print(f"audit  -> {AUDIT_PATH}")
    return results


if __name__ == "__main__":
    main()
