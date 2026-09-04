"""
Experiment 5, Checkpoint 13 — figures.

Only figures supported by real data are produced. No decorative figures.
Reads the committed result JSONs; runs no new analysis.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIG = ROOT / "experiments" / "figures" / "experiment5"
FIG.mkdir(parents=True, exist_ok=True)

PRIM = json.loads((ROOT / "experiments" / "experiment5_primary_results.json").read_text())
ROB = json.loads((ROOT / "experiments" / "experiment5_robustness.json").read_text())
DESC = json.loads((ROOT / "experiments" / "experiment5_descriptive.json").read_text())
PRED = json.loads((ROOT / "experiments" / "experiment5_predictive_results.json").read_text())
RAW = pd.read_csv(ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_irrigation_2004_05_raw.csv")
MAP = pd.read_csv(ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_mapping_table.csv")

C_TN, C_AP, C_TG, C_NEUT = "#2a6f97", "#c1666b", "#e0a458", "#8d99ae"


def fig1_coverage():
    m = MAP.copy()
    m["has_value"] = m.mapping_type != "UNMAPPABLE"
    order = ["Andhra Pradesh", "Telangana", "Tamil Nadu"]
    fig, ax = plt.subplots(figsize=(10, 5))
    y = 0
    ticks, labels = [], []
    for reg in order:
        sub = m[m.harvestwise_region == reg].sort_values("canonical_district_harvestwise")
        for r in sub.itertuples():
            ax.barh(y, 1, color=(C_TN if reg == "Tamil Nadu" else C_AP if reg == "Andhra Pradesh" else C_TG)
                    if r.has_value else "#ffffff",
                    edgecolor="#444", hatch="" if r.has_value else "///")
            ticks.append(y)
            labels.append(f"{r.canonical_district_harvestwise.title()}"
                          + ("" if r.has_value else "  (UNMAPPABLE)"))
            y += 1
        y += 0.6
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xticks([])
    ax.set_xlim(0, 1)
    ax.invert_yaxis()
    ax.set_title("Irrigation coverage by study district — observed year 2004-05 (Fasli 1414)\n"
                 "filled = observed value · hatched = UNMAPPABLE_YEAR_NOT_COVERED", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "01_irrigation_coverage_and_missingness.png", dpi=160)
    plt.close(fig)


def fig2_distributions():
    d = MAP[MAP.mapping_type != "UNMAPPABLE"].merge(RAW, on="source_district_name", how="left")
    d["irrigated_fraction"] = d["pct_net_irrigated_to_net_area_sown"]
    panels = [("net_irrigated_area_ha", "Net irrigated area (ha)"),
              ("gross_irrigated_area_ha", "Gross irrigated area (ha)"),
              ("irrigated_fraction", "% net irrigated to net area sown")]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    order = ["Andhra Pradesh", "Telangana", "Tamil Nadu"]
    cols = {"Andhra Pradesh": C_AP, "Telangana": C_TG, "Tamil Nadu": C_TN}
    for ax, (col, lab) in zip(axes, panels):
        data = [d.loc[d.harvestwise_region == r, col].dropna() for r in order]
        bp = ax.boxplot(data, tick_labels=[r.replace(" ", "\n") for r in order],
                        patch_artist=True, showmeans=True)
        for patch, r in zip(bp["boxes"], order):
            patch.set_facecolor(cols[r])
            patch.set_alpha(0.65)
        for i, s in enumerate(data, 1):
            ax.scatter(np.random.normal(i, 0.05, len(s)), s, s=12, color="#333", alpha=0.6, zorder=3)
        ax.set_ylabel(lab, fontsize=9)
        ax.tick_params(labelsize=8)
    fig.suptitle("District irrigation by region, 2004-05 (points = individual districts)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "02_irrigation_by_region.png", dpi=160)
    plt.close(fig)


def fig3_region_coefficients():
    ms = PRIM["models"]
    names = [("A_region_only", "A\nregion only"),
             ("B_region_plus_exp4_covariates", "B\n+ Exp 4 covariates"),
             ("C_region_plus_covariates_plus_irrigation", "C\n+ irrigation")]
    fig, ax = plt.subplots(figsize=(7.5, 5))
    x = np.arange(3)
    b = [ms[k]["coefficient_t_ha"] for k, _ in names]
    for i, (k, _) in enumerate(names):
        lo_p, hi_p = ms[k]["ci95_plain"]
        lo_c, hi_c = ms[k]["ci95_clustered"]
        ax.plot([i - 0.06, i - 0.06], [lo_p, hi_p], color=C_NEUT, lw=6, solid_capstyle="butt",
                label="plain OLS 95% CI" if i == 0 else None)
        ax.plot([i + 0.06, i + 0.06], [lo_c, hi_c], color=C_TN, lw=6, solid_capstyle="butt",
                label="district-clustered 95% CI (G=31)" if i == 0 else None)
    ax.scatter(x, b, color="black", zorder=5, s=45)
    for i, v in enumerate(b):
        ax.text(i + 0.16, v, f"{v:+.4f}", va="center", fontsize=9)
    ax.axhline(0, color="k", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels([n for _, n in names], fontsize=9)
    ax.set_ylabel("Tamil Nadu region coefficient (t/ha)")
    ax.set_title("Region coefficient across the three pre-registered models\n"
                 "adding irrigation does NOT reduce it", fontsize=11)
    ax.legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(FIG / "03_region_coefficient_A_B_C.png", dpi=160)
    plt.close(fig)


def fig4_incremental():
    po = PRIM["primary_outcome"]
    bs = ROB["R6_cluster_bootstrap"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))

    ax = axes[0]
    shares = [po["experiment4_share_pct"], po["incremental_irrigation_explanation_pct"]]
    ax.bar(["Experiment 4\ncovariates", "Irrigation\n(incremental)"], shares,
           color=[C_NEUT, C_TN if shares[1] > 0 else C_AP])
    ax.axhline(10, ls="--", color="black", lw=1.2,
               label="pre-registered threshold (10 pp)")
    ax.axhline(0, color="k", lw=1)
    for i, v in enumerate(shares):
        ax.text(i, v + (1.2 if v >= 0 else -2.4), f"{v:+.2f}", ha="center", fontsize=10)
    ax.set_ylabel("% of the original regional gap accounted for")
    ax.set_title("Share of the gap accounted for", fontsize=11)
    ax.legend(fontsize=8)

    ax = axes[1]
    # reconstruct the bootstrap distribution summary as an interval plot
    lo, hi = bs["ci95_pct"]
    ax.axvspan(lo, hi, color=C_TN, alpha=0.18, label="bootstrap 95% CI")
    ax.axvline(bs["point_estimate_pct"], color="black", lw=2, label="point estimate")
    ax.axvline(bs["bootstrap_mean_pct"], color=C_TN, lw=1.4, ls=":", label="bootstrap mean")
    ax.axvline(10, color="red", ls="--", lw=1.4, label="threshold 10 pp")
    ax.axvline(0, color="grey", lw=1)
    ax.set_yticks([])
    ax.set_xlabel("Incremental irrigation explanation (percentage points)")
    ax.set_title(f"District-cluster bootstrap ({bs['n_reps_used']} reps)\n"
                 f"P(≥10 pp) = {bs['pr_incremental_ge_10pct']:.3f}", fontsize=11)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "04_incremental_explained_gap.png", dpi=160)
    plt.close(fig)


def fig5_pooled_vs_within():
    a = DESC["yield_association"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, (view, title) in zip(axes, [("A_nearest_year_2004", "View A — irrigation year 2004 only"),
                                        ("B_district_mean_2000_2012", "View B — district mean 2000-2012")]):
        vars_ = list(a[view].keys())
        pooled = [a[view][v]["pooled"].get("pearson_r") for v in vars_]
        wtn = [a[view][v]["within_tamil_nadu"].get("pearson_r") for v in vars_]
        wap = [a[view][v]["within_ap_telangana"].get("pearson_r") for v in vars_]
        y = np.arange(len(vars_))
        h = 0.26
        ax.barh(y - h, pooled, h, label="pooled", color=C_NEUT)
        ax.barh(y, wtn, h, label="within Tamil Nadu", color=C_TN)
        ax.barh(y + h, wap, h, label="within AP + Telangana", color=C_AP)
        ax.axvline(0, color="k", lw=1)
        ax.set_yticks(y)
        ax.set_yticklabels([v.replace("_", " ") for v in vars_], fontsize=8)
        ax.set_xlabel("Pearson r with yield")
        ax.set_title(title, fontsize=10)
    axes[0].legend(fontsize=8, loc="lower left")
    fig.suptitle("Pooled vs within-region association — all four variables flagged "
                 "POTENTIAL_GEOGRAPHIC_CONFOUNDING", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "05_pooled_vs_within_region.png", dpi=160)
    plt.close(fig)


def fig6_robustness():
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))

    ax = axes[0]
    r1 = ROB["R1_alternative_definitions"]
    ks = list(r1.keys())
    vals = [r1[k]["incremental_pct"] for k in ks]
    ax.barh([k.replace("_", " ") for k in ks], vals,
            color=[C_TN if v > 0 else C_AP for v in vals])
    ax.axvline(10, ls="--", color="black", lw=1.2, label="threshold 10 pp")
    ax.axvline(0, color="k", lw=1)
    for i, v in enumerate(vals):
        ax.text(v + (0.6 if v >= 0 else -0.6), i, f"{v:+.1f}", va="center",
                ha="left" if v >= 0 else "right", fontsize=8)
    ax.set_xlabel("Incremental irrigation explanation (pp)")
    ax.set_title("R1 — every irrigation definition is negative", fontsize=10)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=8)

    ax = axes[1]
    lodo = pd.DataFrame(ROB["R5_leave_one_district_out"]["results"]).sort_values("incremental_pct")
    ax.barh(lodo.district_left_out.str.title(), lodo.incremental_pct, color=C_NEUT)
    hy = lodo[lodo.district_left_out == "HYDERABAD"]
    if len(hy):
        ax.barh(["Hyderabad"], hy.incremental_pct.values, color=C_AP,
                label="Hyderabad (published zero-irrigation extreme)")
        ax.legend(fontsize=8, loc="lower right")
    ax.axvline(10, ls="--", color="black", lw=1.2)
    ax.axvline(0, color="k", lw=1)
    ax.set_xlabel("Incremental irrigation explanation (pp)")
    ax.set_title("R5 — leave-one-district-out: 0 of 31 folds reach the threshold", fontsize=10)
    ax.tick_params(labelsize=6)
    fig.tight_layout()
    fig.savefig(FIG / "06_robustness.png", dpi=160)
    plt.close(fig)


def fig7_predictive():
    arms = PRED["arms"]
    ks = list(arms.keys())
    labels = [k.split("_", 1)[1].replace("_", " ") for k in ks]
    mae = [arms[k]["mae_mean"] for k in ks]
    mae_sd = [arms[k]["mae_std"] for k in ks]
    r2 = [arms[k]["r2_mean"] for k in ks]
    r2_sd = [arms[k]["r2_std"] for k in ks]
    colors = [C_NEUT, C_TN, C_TN, "#5c9e31", C_AP, C_AP, C_AP]
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8))
    for ax, vals, sds, lab, base in ((axes[0], mae, mae_sd, "MAE (t/ha), lower is better", mae[0]),
                                     (axes[1], r2, r2_sd, "R² , higher is better", r2[0])):
        ax.bar(labels, vals, yerr=sds, capsize=4, color=colors, alpha=0.9)
        ax.axhline(base, ls="--", color=C_NEUT, lw=1.2, label="baseline")
        ax.set_ylabel(lab)
        plt.setp(ax.get_xticklabels(), rotation=28, ha="right", fontsize=7)
        ax.legend(fontsize=8)
    axes[1].axhline(0, color="k", lw=1)
    fig.suptitle("Cross-region predictive transfer AP+Telangana → unseen Tamil Nadu districts "
                 "(5 seeds; arm 7 is the mandatory shortcut control)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "07_predictive_transfer.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    fig1_coverage(); fig2_distributions(); fig3_region_coefficients()
    fig4_incremental(); fig5_pooled_vs_within(); fig6_robustness(); fig7_predictive()
    print("figures written ->", FIG)
    for p in sorted(FIG.glob("*.png")):
        print("  ", p.name)
