# HarvestWise — Consolidated scientific synthesis, Experiments 1–9

**Synthesis only.** No experiment was run, no prior report or pre-registration was modified, no
dataset or model code was touched. Every number below is quoted from the existing repository
record; where a figure is a post-hoc integration across experiments rather than a finding of any
single one, it is labelled as such.

| Field | Value |
|---|---|
| Git HEAD at writing | `b6e69b9` (Experiment 9 finalization) |
| Branch | `main`, synchronized with origin |
| Source material | `experiments/*.md`, `experiments/*.json`, `README.md`, `RESULTS.md`, `paper/HarvestWise_paper.md` |

---

## 0. A note on scope — two distinct evaluation tracks

The project contains **two separate evaluation lineages** that must not be conflated, because they
use different units, samples and splits:

- **Field-level track** — `RESULTS.md`, `README.md`, `EXPERIMENT_1_REPORT.md`, `paper/`. Unit is a
  *(field, season)*; the headline held-out sample is **21–28 real season examples**. This is where
  the naive-baseline comparison and the fusion ablation live.
- **District-level track** — `UNSEEN_DISTRICT_EXPERIMENT_REPORT.md` and Experiments 2–9. Unit is a
  *(district, year)*; samples run 359–561 rows. This is where domain shift, the regional yield gap,
  irrigation, rainfall and temperature are studied.

Statements about "the model" from one track do not transfer to the other. This synthesis keeps
them separate throughout.

---

## 1. Master table — Experiments 1–9

| # | Question | Dataset / sample | Method | Main result | Statistical status | Robustness status | Supports | Does NOT support | Key limitation |
|---|---|---|---|---|---|---|---|---|---|
| **1a** | Can a multimodal model forecast yield better than trivial baselines? | 21 real *(field, season)* examples; chronological split | MLP fusion vs naive / RF / XGBoost | **Naive mean is best: 0.689 ± 0.006 MAE**; RF 0.726 ± 0.098; HarvestWise 0.727 ± 0.131; XGBoost 0.764 ± 0.181 | Negative result, multi-seed | Stable across seeds; earlier positive single-seed claims **retracted** | A rigorous negative result | Any accuracy advantage for the multimodal architecture | n = 21; regional-average labels |
| **1b** | Do modalities contribute, or is soil a field-identity shortcut? | Same 21 examples | Soil-only control vs full fusion | Soil-only MAE 0.093 ≈ full multimodal 0.085 | Controlled comparison | Corroborated by SHAP (`RESULTS.md` §5e) | **Soil acts as a field-identity shortcut** | Weather/satellite contributing separable signal | Small n; control is the informative part |
| **1c** | Does the model generalize to **unseen districts**? | 561 district-years, 5 seeds, grouped split | Repeated stratified grouped split | Baseline 0.5990; **weather+satellite best 0.5255 (R² 0.205)**; full multimodal 0.5627 | Modest improvement over baseline | 5 seeds; sd 0.08–0.12 overlaps | Weather+satellite beating the mean **in this split** | Full multimodal superiority (it is worse than weather+satellite) | Soil-only is worst (0.7557), consistent with 1b |
| **2** | Why does performance collapse on Tamil Nadu? | 487 train / 74 test district-years | AP+TG → TN transfer | Baseline 0.9327 **best**; full multimodal 0.9389; all models ≥ baseline | Diagnostic, negative | Consistent across arms | Existence and size of a TN performance gap | Any model beating the mean under this shift | **Confounded**: cross-region *and* temporal shift, explicitly labelled so |
| **3** | Can geography be isolated from era/season? | 239 train / 143 test district-years, 2000–2012 | Overlap-year recovery; pure-geography isolation | **Baseline 1.0523 best**; weather 1.0549; full multimodal 1.1340; all R² < 0 | Isolation achieved; models negative | Consistent | **Pure geographic shift isolated** — the design succeeded | Any model generalizing across region once era is held fixed | Isolation 2 bounds era+season *jointly*, not separately |
| **4** | Do geographic covariates explain the regional yield gap? | 382 Kharif district-years, 32 districts | Ridge + pre-stated region-proxy screen | Raw gap **0.8250 t/ha**; covariates account for **≈31.6 %** | Partial explanation | `n_rice_seasons` caught as a **perfect region proxy** (ICC 1.000, KS 1.000) | That ~⅓ of the gap tracks measurable geography | A mechanism for the remaining ~⅔ | Static covariates; screen was essential |
| **5** | Does district irrigation explain the residual gap? | 378 district-years, 31 districts | Cross-sectional, 13-checkpoint protocol | β_A 0.8340; irrigation coefficient **−0.0057** (wrong direction) | **LITTLE OR NO SUPPORT** | Multiple robustness arms | An informative negative | Irrigation as an explanation of the gap | Irrigation observed in **one year**, broadcast across the panel |
| **6** | Within districts, does irrigation change yield? | 54 rows → **27 first-differences**, 2 periods | First-difference / two-way FE, wild bootstrap | β **+0.0121**, CI **[−0.0536, +0.0778]**, p 0.7193 | **INCONCLUSIVE** | FD ≡ two-way FE; rounding-insensitive | That fingerprinting was eliminated by differencing | Either an effect **or** its absence | **Underpowered**: CI contains both 0 and the anchor |
| **7** | Does fertilizer intensity explain the gap? | none built | Feasibility investigation only | Not modelled | **NOT FEASIBLE** | n/a | A documented feasibility boundary | Anything about fertilizer and yield | AP "distribution" vs TN "consumption" confounded with region; one year only |
| **8** | Does intra-seasonal **rainfall structure** add information beyond the seasonal total? | 359 district-years, 31 districts, 13 years | Two-way FE, 5-df joint Wald, wild cluster bootstrap | Wald 7.658; **bootstrap p 0.3418**; incremental within-R² **0.0273** (threshold 0.031) | **INCONCLUSIVE** | Arms range p 0.002–0.772 | Pre-registration executed faithfully | Rainfall structure adding value **or** being irrelevant | **Confirmed** terrain-correlated ERA5–IMD disagreement (TN r 0.446 vs AP 0.770, TG 0.751) |
| **9** | Does within-season **temperature structure** add information beyond seasonal mean temperature? | 359 district-years, 31 districts, 13 years | Pre-registered two-way FE; restricted wild cluster bootstrap | β **+0.17195** t/ha per SD; **p 0.0211**; CI **[+0.0422, +0.3233]** | **SUPPORTED** under the pre-registered criterion | **FRAGILE** — R1 β −0.1263 (p 0.0034), R2 β −0.0906 (p 0.0159), R5 β +0.0059 (p 0.9408) | That the pre-registered criterion was met | Robustness, causality, or practical usefulness | Sign reverses without year FE; vanishes on balanced panel; null in both regions separately |

---

## 2. Experiment-by-experiment interpretation

### Experiment 1 — Baselines, ablation and unseen-district generalization

Three distinct findings, each supported by its own evidence.

**1a — no model beats the mean.** On the headline held-out sample of 21 real season examples,
the **naive mean-predictor has the lowest MAE (0.689 ± 0.006)**. HarvestWise (0.727 ± 0.131) is
statistically indistinguishable from Random Forest (0.726 ± 0.098), and its variance is roughly
20× the naive baseline's. Two earlier positive claims are **retracted on the record**
(`RESULTS.md` §"Retractions"): one was seed luck; the other rested on satellite data that was
**56 % gap-filled**, and interpolated series are artificially smooth and therefore easy to predict.

**1b — soil is a field-identity shortcut.** A model given *only* the static 5-value soil vector —
no input that varies within a field across seasons — scores MAE 0.093, statistically
indistinguishable from the full multimodal model's 0.085. Since the soil-only model cannot be
forecasting a season-specific outcome, this is direct evidence that weather and satellite
contribute essentially nothing beyond noise at this sample size. SHAP on the Random Forest
independently attributes an order of magnitude more importance to per-field-constant soil features
than to any weather or NDVI feature.

**1c — a genuine but narrow generalization result.** On the district-level grouped split (561
rows, 5 seeds), **weather+satellite achieves MAE 0.5255 with R² 0.205, better than the baseline's
0.5990**. This is the project's clearest positive predictive result. Two qualifications: the
**full multimodal model is worse** (0.5627) than the two-modality combination, so fusion is not
what produces the gain; and soil-only is the *worst* configuration here (0.7557), consistent with
1b's finding that soil supplies identity rather than signal.

### Experiment 2 — Tamil Nadu domain shift

Training on AP+Telangana and testing on Tamil Nadu, **no model beats the baseline** (0.9327);
the full multimodal model reaches 0.9389. The report explicitly labels this **CROSS-REGION +
TEMPORAL DOMAIN SHIFT**, not pure geographic generalization, because at that stage TN data came
from a different era. The feature shift across regions was measured as roughly **5× larger** than
the within-AP/TG shift between its own 1999–2005 and 2006–2012 halves — consistent with the gap
being more than decade-scale drift, but the report itself states this does not isolate geography.

### Experiment 3 — Overlap recovery and isolation

The methodologically most successful experiment. By recovering overlapping years, it constructed a
**pure geographic contrast**: same years (2000–2012), same season, same Landsat era, differing only
in state — 239 training rows across 20 districts, 143 test rows across 12.

The result is negative and clean: **the baseline (MAE 1.0523) beats every model**, full multimodal
worst among the informative configurations at 1.1340, and **all R² are below zero**. Once era and
season are held fixed, no configuration generalizes across region. Isolation 2 bounds the era and
season contributions **jointly** and does not separate them — a limitation the report states.

### Experiment 4 — Geographic covariates and the regional gap

The raw AP/TG-versus-TN Kharif yield gap is **0.8250 t/ha**. Geographic covariates account for
**≈31.6 %** of it. The lasting contribution is methodological: a **pre-stated region-proxy screen**
caught `n_rice_seasons` as a perfect region proxy (ICC 1.000, KS 1.000, |SMD| → ∞) — a reporting
convention that would otherwise have masqueraded as agronomy. That screen has been applied in every
subsequent experiment and has repeatedly earned its place.

### Experiment 5 — District irrigation and the residual gap

Executed under a 13-checkpoint approval protocol. The irrigation coefficient is **−0.0057** — the
*wrong direction* — and the verdict is **LITTLE OR NO SUPPORT**. Irrigation does not explain the
residual regional gap. The binding limitation is that irrigation was observed in a **single year**
and broadcast across a 13-year panel, making the variable effectively static per district.

### Experiment 6 — Within-district irrigation

A two-period within-district design that **eliminated district fingerprinting by construction**,
with first-difference and two-way fixed effects shown to be exactly equivalent. Result:
**β = +0.0121, CI [−0.0536, +0.0778], bootstrap p 0.7193 — INCONCLUSIVE.**

The confidence interval contains both zero **and** the pre-registered meaningful-effect anchor, on
just **27 first-differences**. This is the project's cleanest statement of an underpowered design:
it establishes neither an effect nor its absence. It also did **not** test Experiment 5's
cross-region question — `is_tn` is time-invariant and absorbed by district fixed effects.

### Experiment 7 — Fertilizer intensity

**NOT FEASIBLE**, and the discovery phase *succeeded*: 31 of 32 study districts, both regions,
same year, compatible units, validated denominators. The experiment was rejected because AP
publishes "Distribution of Fertilizers" and TN publishes "Consumption of Chemical Fertilizers",
the definitions could not be shown equivalent, and **that difference is confounded exactly with the
AP/TN contrast being measured**. With only one matched year, no within-district design could
neutralise it. This is the clearest demonstration in the project that **data availability is not
experimental feasibility**.

### Experiment 8 — Intra-seasonal rainfall structure

Pre-registered before data construction. Joint 5-df Wald 7.658; **bootstrap p 0.3418**; incremental
within-R² **0.0273** against a pre-registered threshold of 0.031 — **INCONCLUSIVE**. Robustness
ranged from p 0.002 to p 0.772 across defensible specifications.

Its most consequential output was not the hypothesis test but the **measurement finding**:
independent validation against IMD gridded rainfall showed within-district agreement of **0.446 in
Tamil Nadu against 0.770 (AP) and 0.751 (TG)**. That was recorded as a **confirmed limitation of
Experiment 8** and an **audit flag only** for earlier experiments — explicitly not a retroactive
invalidation.

### Experiment 9 — Temperature structure

The most methodologically complete experiment: measurement validation first, then pre-registration
frozen by SHA-256, then estimation, then independent audit.

**Primary result: β = +0.17195 t/ha per SD, bootstrap p 0.0211, CI [+0.0422, +0.3233].** All three
pre-registered conditions met → **SUPPORTED**.

**And specification-fragile.** Removing year fixed effects **reverses the sign** to −0.1263
(p 0.0034); region trends likewise (−0.0906, p 0.0159); the **balanced panel yields +0.0059
(p 0.9408)** — the association disappears; and **neither region alone is statistically supported**
(AP+TG p 0.1843; TN p 0.1965). Two secondary constructs survive Holm correction **with opposite
signs** (`t_p95_tmax` +0.3670; `tdays_gt30_tmax` −0.3321).

What held: the measurement-limitation sensitivities R3 (+0.1638) and R3b (+0.1539), and
leave-one-out stability across all 44 refits.

**The canonical characterisation, to be quoted in full wherever Experiment 9 is cited:**

> **SUPPORTED UNDER THE PRE-REGISTERED PRIMARY SPECIFICATION, BUT SPECIFICATION-FRAGILE**

It must not be shortened to "temperature effect supported", and it is neither a causal claim nor
evidence that temperature structure improves predictive performance — Experiment 9 measured an
association and never evaluated prediction.

---

## 3. Cross-experiment questions — answered explicitly

**1. Does HarvestWise demonstrate better real-world yield prediction than the naive baseline?**
**No, not on the headline sample.** Naive 0.689 ± 0.006 is the best of four models; HarvestWise
0.727 ± 0.131. On the separate district-level unseen split, **weather+satellite (0.5255) does beat
the baseline (0.5990)** — a real but narrower result, on a different unit of analysis, and not the
full architecture.

**2. Does multimodal fusion demonstrate robust predictive superiority?** **No.** The 5-seed
ablation puts **fused (R² −0.069) below imagery-only (0.027)**, with all three at or below zero.
The earlier 3-seed result favouring fusion is **retracted**. In the district split, the full
multimodal model (0.5627) is beaten by weather+satellite (0.5255). Fusion is not currently
demonstrated to help anywhere in the record.

**3. Does the evidence establish that geographic/domain shift explains the TN gap?** **Partly, and
better than Experiment 2 alone could.** Experiment 2's contrast was explicitly confounded with
time. **Experiment 3 isolated pure geography** and still found every model below baseline, which
does establish that a genuine cross-region generalization failure exists independent of era. What
remains unexplained is the *mechanism*.

**4. How much of the regional yield gap do geographic covariates explain?** **≈31.6 % of an 0.8250
t/ha raw gap** (Experiment 4). Roughly two-thirds remains unexplained.

**5. Does irrigation explain the residual gap?** **No.** Experiment 5's coefficient was −0.0057,
the wrong direction, verdict LITTLE OR NO SUPPORT.

**6. Is the irrigation → yield relationship established?** **No — and it is not refuted either.**
Experiment 6 is **INCONCLUSIVE**, with a CI containing both zero and the meaningful-effect anchor
on 27 first-differences. Neither an effect nor its absence is established.

**7. Is fertilizer intensity usable as a clean explanatory variable?** **No.** NOT FEASIBLE — a
definitional mismatch confounded with the regional contrast, and only one matched year.

**8. Does rainfall structure have established predictive/associational value?** **No.** Experiment
8 is INCONCLUSIVE: p 0.3418, incremental R² below threshold. Note this does **not** mean rainfall
structure is irrelevant — the design could not distinguish that from no effect.

**9. Does temperature structure have established associational value?** **Under the pre-registered
specification, yes** — β +0.17195, p 0.0211, criterion met. This is a genuine pre-registered
positive result and the only one in the project.

**10. Is the temperature result robust?** **No.** The sign reverses without year fixed effects
(−0.1263, p 0.0034); the balanced panel gives +0.0059 (p 0.9408); neither region alone is
supported; two secondaries disagree in sign. The finding is **supported but specification-fragile**,
and those two words must always travel together.

**11. Is there evidence for causality anywhere in Experiments 1–9?** **No. Nowhere.** Every design
is observational. Weather variables (Experiments 8, 9) are meteorologically exogenous to yield,
which strengthens *plausibility* and rules out reverse causation from yield to rainfall — but
exogeneity of a regressor is not an identification strategy, and no experiment employed one. No
causal claim is licensed by any result in this project.

**12. What is the strongest scientifically defensible claim the project can make today?**

> HarvestWise is a rigorously executed **negative-and-inconclusive-results program** in
> district-level crop-yield modelling for southern India. It establishes, with pre-registration,
> leakage auditing and independent measurement validation, that (a) multimodal deep fusion does not
> beat a mean-predictor or tree ensembles on regional-average labels, with the mechanism identified
> as a static field-identity shortcut; (b) a genuine cross-region generalization failure exists
> even after geography is isolated from era; (c) roughly a third of the AP/TG-versus-TN yield gap
> tracks measurable geography, while irrigation does not explain the remainder; and (d) commonly
> assumed climate predictors are far harder to validate than the literature implies — one candidate
> was infeasible on definitional grounds, one inconclusive, and one supported only under a single
> specification. Alongside this, the project contributes a reusable ERA5-derived Climate-Shock
> Benchmark and an RL harvest-timing policy that **matches** a full-foresight optimizer under a
> 4-week information constraint.

The methodological infrastructure — pre-registration with hash freezing, region-proxy and ICC
screens, independent two-product measurement validation, and cited-not-stored provenance — is
arguably the project's most transferable contribution.

---

## 4. Robustness hierarchy

### A. Strongest evidence

- **The negative predictive result (1a)** — multi-seed, replicated, with two earlier positive claims retracted. Negative results this well-defended are rare.
- **Soil as field-identity shortcut (1b)** — a *controlled* result: the soil-only model cannot forecast season-specific outcomes yet matches full fusion. Independently corroborated by SHAP.
- **Pure geographic isolation (Experiment 3)** — a clean design that answered its question, even though the answer was negative.
- **The RL harvest-window information-constraint result** — 28 paired trajectories, Wilcoxon p 0.317: matches a full-foresight optimizer. The defensible claim is *matching under an information constraint*, never *outperforming*.

### B. Supported but fragile

- **Experiment 9 temperature structure** — pre-registered criterion met, sign reverses under an alternative specification, vanishes on the balanced panel. Belongs here and nowhere else.
- **Weather+satellite beating baseline on unseen districts (1c)** — a real improvement (0.5255 vs 0.5990, R² 0.205), but on 5 seeds with overlapping spreads, and not reproduced by the full architecture.

### C. Inconclusive

- **Experiment 6 irrigation within districts** — CI contains both 0 and the anchor; 27 first-differences.
- **Experiment 8 rainfall structure** — p 0.3418, incremental R² 0.0273 below the 0.031 threshold.

### D. Null / no support

- **Experiment 5 irrigation and the regional gap** — coefficient in the wrong direction; LITTLE OR NO SUPPORT. Closest thing in the project to an informative null, though it is not a *precise* null.
- **Multimodal fusion benefit** — fused below imagery-only across 5 seeds.

### E. Feasibility only

- **Experiment 7 fertilizer** — NOT FEASIBLE. No estimate exists and none should be quoted.

### F. Measurement limitation

- **Terrain-correlated ERA5–IMD disagreement** — rainfall (TN r 0.446 vs 0.770 / 0.751, confirmed in Experiment 8) and, more mildly, temperature (TN 0.705 vs 0.873 / 0.818, Experiment 9). Tracks the Western Ghats rain-shadow interior rather than administrative boundaries. Standing as an **audit flag** for prior experiments using ERA5-derived weather features — **not** a retroactive invalidation.

Experiments 2 and 4 sit deliberately across categories: Experiment 2 is a strong *diagnostic* whose transfer result is negative and whose contrast is confounded; Experiment 4 is a partial explanation (~31.6 %) plus a strong methodological contribution (the region-proxy screen).

---

## 5. What Experiments 1–9 HAVE established

**Prediction.** That a multimodal deep model does **not** beat a mean-predictor or tree ensembles
for district/regional-average yield labels at this sample size — replicated across seeds, with the
mechanism identified. That on an unseen-district grouped split, **weather+satellite does beat the
baseline** (0.5255 vs 0.5990, R² 0.205), while the full architecture does not.

**Mechanism of failure.** That static per-field soil features function as an **identity shortcut**:
a soil-only model matches full fusion despite having no season-varying input at all.

**Generalization.** That a **genuine cross-region generalization failure** exists, isolated from era
and season by Experiment 3's design, with every configuration below baseline and all R² < 0.

**Regional gap.** That the raw gap is **0.8250 t/ha** and geographic covariates account for
**≈31.6 %** of it; and that **irrigation does not explain the remainder**.

**Feasibility boundaries.** That fertilizer intensity **cannot** currently support a defensible
cross-region experiment, for reasons of definitional comparability confounded with region.

**Measurement.** That two independently constructed weather products **disagree in a
terrain-correlated way** over the Western Ghats rain-shadow interior — established for rainfall,
milder for temperature, and quantified in both cases.

**Method.** That pre-registration with hash freezing, pre-stated ICC and region-proxy screens,
independent measurement validation, and cited-not-stored provenance are **operable in practice** —
and that they work: the `n_rice_seasons` proxy, the heat-stress zero-inflation defect, and the TN
rainfall disagreement were all caught by screens stated in advance.

**Policy.** That an RL harvest-timing policy **matches** a full-foresight optimizer under a 4-week
information constraint (28 paired trajectories, Wilcoxon p 0.317).

## 6. What Experiments 1–9 have NOT established

**Prediction superiority.** No claim that HarvestWise is accurate, state-of-the-art, or superior to
any baseline is supported. On the headline sample it is **third of four**, behind the naive mean.

**Multimodal fusion.** No benefit from fusion is demonstrated anywhere. Fused is **below**
imagery-only across 5 seeds, and below weather+satellite on the district split.

**Causal effects.** **Nothing causal is established anywhere in Experiments 1–9.** No design used
an identification strategy. Exogeneity of weather is not identification.

**Climate adaptation.** The project's title promises "Climate-Adaptive" forecasting. **No result
supports meaningful climate adaptivity.** `RESULTS.md` §8 lists climate sensitivity as an open
problem, and Experiments 8 and 9 — the two direct tests of climate structure — returned
INCONCLUSIVE and SUPPORTED-BUT-FRAGILE respectively.

**Irrigation effects.** Neither established (Experiment 6 inconclusive) nor refuted. Experiment 5
establishes only that irrigation does not explain the *regional gap*.

**Rainfall effects.** Experiment 8 does **not** establish that intra-seasonal rainfall structure
adds value, and equally does **not** establish that it is irrelevant.

**Temperature effects.** Experiment 9 establishes that a pre-registered criterion was met. It does
**not** establish robustness, a mechanism, causality, or practical usefulness. The positive sign
was not predicted in advance and remains unexplained; two secondary constructs disagree in sign.

**Generalization.** No configuration generalizes across region once era is held fixed.

**Regional mechanisms.** Roughly **two-thirds of the 0.8250 t/ha gap remains unexplained** after
geography, irrigation, fertilizer (infeasible), rainfall structure (inconclusive) and temperature
structure (fragile) have each been examined.

---

## 7. Research gaps

### A. Data limitations
The binding constraint throughout. **359–561 rows** at district level; **21–28** at field level;
27 first-differences in Experiment 6. Irrigation and fertilizer each exist for **one usable year**.
Tamil Nadu has **zero** Rabi rows, foreclosing any cross-region Rabi design.

### B. Measurement limitations
Terrain-correlated ERA5–IMD disagreement, confirmed for rainfall and present in temperature. **No
third independent product exists in the repository**, so it is impossible to say which product is
closer to truth — only that they disagree. Satellite observation density is region-correlated
(TN 17.5 % thin rows against TG 0.9 %), which independently disqualified phenology constructs.

### C. Statistical limitations
Chronic low power. Experiment 6 could not separate zero from the anchor; Experiment 9 was declared
marginally powered for A1 and **not powered** for A2 *in advance*. With 31 clusters, asymptotic
inference is unreliable — Experiment 8 showed an asymptotic p 0.0001 becoming a bootstrap p 0.180.

### D. Model limitations
No architecture has beaten a mean-predictor on the headline sample. The identity-shortcut mechanism
means added modalities have not translated into signal. **Backend checkpoints
(`fusion_backbone.pt`, 135,696 params) carry no record of whether they were trained on real or
synthetic data** — `training/train_forecast_model.py` supports a `--synthetic` smoke-test mode, and
the artefacts do not distinguish the two.

### E. Causal-identification limitations
The largest conceptual gap. No instrument, no natural experiment, no discontinuity, no staggered
adoption. Experiment 6's within-district differencing is the closest approach and was underpowered.

### F. Validation limitations
No external validation on a region or period outside the AP/TG/TN 2000–2012 panel. No temporal
hold-out (train early years, test later ones). The balanced-panel result in Experiment 9 suggests
panel composition matters substantially and has never been examined directly.

---

## 8. Next-experiment recommendation

### Candidates considered

| Candidate | Assessment |
|---|---|
| **Stronger predictive validation** | Directly targets the project's weakest claim. Data already in hand. |
| **Balanced-panel predictive validation** | Experiment 9's R5 showed panel composition changes conclusions — currently unexamined. Overlaps heavily with the above. |
| **Improved temperature/rainfall measurement** | Needs a third product not in the repository; would be acquisition, not experiment. Deferrable. |
| **Temporal generalization** | Genuinely untested, cheap, and directly relevant to a forecasting claim. |
| **Mechanism identification** | Attractive but premature: the Experiment 9 sign is unexplained and fragile; chasing a mechanism for an unstable association risks rationalising noise. |
| **Causal design** | No instrument or quasi-experiment is available in the data. **Not currently possible.** |
| **External validation** | No external region/period dataset is in the repository. Would require new acquisition and approval. |
| **Harvest-window policy validation** | The policy result already holds and is honestly framed; extending it does not address the project's weakest claims. |

### Recommendation

**A predictive-validation experiment combining temporal generalization with panel-composition
sensitivity, on the existing 359-row district panel.**

1. **Research question.** Does any model configuration — naive, ridge, tree ensemble, or the
   multimodal architecture — achieve out-of-sample predictive accuracy better than a mean-predictor
   when evaluated by **forward-chaining temporal splits** (train on years ≤ *t*, test on *t+1*), and
   is that conclusion stable across balanced versus unbalanced panel compositions?

2. **Why it matters.** Prediction is what the project is *named for* and what a paper reviewer will
   probe first. Every predictive claim currently rests on **random or grouped** splits, never on the
   forward-in-time evaluation a forecasting system actually faces.

3. **Which limitation it addresses.** Validation limitation F directly, model limitation D, and
   part of statistical limitation C — a forward-chaining design yields up to 12 evaluation folds
   rather than 5 seeds of the same split.

4. **Required data.** **None new.** `experiment9_temperature_panel.csv`, the v2 multimodal dataset,
   and existing weather/satellite/soil features suffice. No Earth Engine quota, no government
   sources, no acquisition approval.

5. **Evaluation strategy.** Forward-chaining across 2000–2012; primary metric MAE against a
   train-mean baseline computed within each fold; report MAE, RMSE, R² per fold and pooled; run
   twice — once on the full 359-row panel and once on the balanced 221-row panel — with the
   difference itself a pre-registered outcome.

6. **Pre-registration requirement.** Mandatory, following the Experiment 9 template: freeze by
   SHA-256 before estimation; fix model configurations, fold structure, metric, baseline and
   decision rule in advance; state power/precision expectations; **and — learning from Experiment
   9's `criterion()` defect — pre-specify a direction condition for any comparative claim.**

7. **Success criterion.** A configuration is deemed to beat the baseline only if its mean MAE is
   lower **and** the difference exceeds fold-to-fold variability by a pre-registered margin
   **and** the direction is consistent in a pre-registered majority of folds. Beating the baseline
   in a single fold, or on average with overlapping spreads, does **not** qualify.

8. **Major risks.** (i) **Most likely outcome is another negative result** — that is acceptable and
   arguably expected. (ii) Early folds have few training years, so early-fold MAE will be noisy;
   the pre-registration must fix a minimum training window. (iii) The 2000–2012 yield trend could
   flatter or penalise forward-chaining; year-trend handling must be fixed in advance. (iv) Sample
   size remains the binding constraint and this experiment does not relieve it.

**A causal experiment is explicitly not recommended** at this time: the data contains no
identification strategy, and attempting one would produce exactly the kind of overclaim this
project has twice retracted.

---

## 9. README / RESULTS / paper consistency

**Reported only. No file was edited.**

### Fully supported

- `RESULTS.md` §9 "What is NOT established" and §10 "What IS established" are accurate and align with this synthesis.
- `RESULTS.md` §2 headline table (naive 0.689 best) and its Retractions section — exemplary practice.
- `RESULTS.md` §6 harvest-window framing: *"a policy with a 4-week forecast horizon matches a grid search with full-season foresight — an information-constraint result, not an accuracy win."*
- `paper/HarvestWise_paper.md` line 235: *"No model beats predicting the mean."*
- `README.md` lines 51–75, which state the negative result and the fusion retraction plainly.

### Supported but needing qualification

- Neither `README.md` nor `RESULTS.md` mentions **Experiments 4–9 at all**. The regional-gap decomposition, the irrigation results, the fertilizer infeasibility, and the rainfall and temperature findings are absent from the project's public-facing documents. Not an error, but the headline documents no longer represent the project's evidence base.
- `README.md` line 108 recommends framing the paper around "RL harvest-window policy + climate-shock benchmark + real-outcome validation." That remains defensible, but should now also carry the Experiments 4–9 methodological programme, which is stronger than any single result in it.

### Outdated / internally contradictory — **the one material finding**

- **`README.md` line 29 contradicts `README.md` line 66.** The status table asserts:
  *"Baselines + ablation | Done - multi-seed ablation shows fusion beats single-modality (R2 0.500 vs 0.444 / 0.441)"* — while the body of the same file states that this exact 3-seed run *"was seed luck and is retracted"*, replacing it with fused −0.069 **below** imagery-only 0.027.
  **A retracted claim is still live in the README's summary table.** It is the first thing a reader
  encounters and it asserts the opposite of the project's actual finding. This is the single most
  consequential documentation inconsistency found.

- **Sample-size divergence.** `README.md` reports the held-out comparison on **28** examples
  (naive 0.672, HarvestWise 0.681); `RESULTS.md` reports **21** (naive 0.689, HarvestWise 0.727).
  Both conclude the model does not beat naive, so the conclusion is unaffected — but the two
  documents quote different numbers for what a reader will take to be the same result.

### Potentially overstated

- The project title, *"Climate-Adaptive Crop Yield Forecasting"*, is not supported by the evidence: `RESULTS.md` §8 lists climate sensitivity as an open problem, and the two direct tests returned INCONCLUSIVE (Experiment 8) and SUPPORTED-BUT-FRAGILE (Experiment 9). The framing is aspirational rather than demonstrated.
- `paper/HarvestWise_paper.md` retains **placeholder author fields** (`[Author Name]`, `[author email]`). A long-standing gap, unrelated to scientific validity but blocking submission.

---

## 10. No-hindsight statement

Each experiment above is described according to **its own original design, pre-registration and
evidence**. Experiment 9's results have not been used to reinterpret or rewrite the conclusions of
Experiments 1–8, and no prior verdict has been changed. Experiment 8's INCONCLUSIVE stands;
Experiment 6's INCONCLUSIVE stands; Experiment 5's LITTLE OR NO SUPPORT stands; Experiment 7's NOT
FEASIBLE stands.

**Sections 3, 4, 5, 6, 7 and 8 of this document are post-hoc integration across experiments.** They
identify patterns visible only in retrospect — the recurrence of identity-shortcut failures, the
recurrence of region-correlated measurement defects, and the chronic power constraint. These
patterns are offered as synthesis, not as findings of any individual experiment, and none of them
is claimed to have been pre-registered.

---

*Synthesis written at Git HEAD `b6e69b9`. No experiment was run; no prior artefact was modified.*
