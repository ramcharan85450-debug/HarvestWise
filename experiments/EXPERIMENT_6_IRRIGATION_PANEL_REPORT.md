# Experiment 6 — Do within-district changes in irrigation track changes in rice yield?

**FINAL PRIMARY OUTCOME: INCONCLUSIVE**

Results: `experiment6_results.json` · Panel: `data/raw/external/district_irrigation/irrigation_panel_2year.csv` · Panel validation: `irrigation_panel_2year_validation.json`
Code: `ingestion/irrigation_panel_2year.py`, `experiments/run_experiment6_analysis.py`

Experiments 1–5 are unchanged. The modelling dataset (`district_multimodal_examples.csv`, `_v2.csv`) was **not** modified; the irrigation panel was never merged into it.

---

## 1. What this experiment does — and what it explicitly does not

Experiment 5 tested whether district irrigation explained the residual Tamil Nadu regional yield association, and returned **LITTLE OR NO SUPPORT**. Its central acknowledged weakness was that irrigation was observed in **one year only (2004-05)** and applied as a **static district attribute** across 2000–2012, which meant 31% of rows paired yield with a later-year irrigation figure and irrigation functioned as a one-to-one district identifier.

Experiment 6 removes that weakness by constructing a genuine **two-year panel** and identifying from **within-district change**.

> ### ⚠️ Experiment 6 does NOT test or replicate the Experiment 5 regional-gap question.
>
> Under a within-district design, `is_tn` is **time-invariant and absorbed by the district fixed effects**. The region coefficient is therefore **inestimable**, and Experiment 5's incremental statistic `((β_B − β_C)/β_A) × 100` is **not computable here**. This was established at Checkpoint 5, before any model was run.
>
> The question actually asked is: **are within-district changes in irrigation associated with within-district changes in rice yield?**

## 2. Hypotheses (pre-registered at Checkpoint 5)

- **H0** — Within-district changes in net irrigated share are not associated with within-district changes in Kharif rice yield, after absorbing district and period effects.
- **H6-E** — Within-district increases in net irrigated share are associated with within-district increases in Kharif rice yield.

## 3. Panel construction

Two DES publications per region, all retrieved, hashed and identity-validated:

| Cell | Publication | Net irrigated area | Unit |
|---|---|---|---|
| AP/TG 2004-05 | DES AP, *Season & Crop Report 2004-05 / 1414 Fasli*, Table III-B (Concld.), p.170 | published | hectares |
| AP/TG 2011-12 | DES AP, *Districts at a Glance 2012*, pp. 17/22/23 | **derived** = gross − more-than-once | **'000 Hect. → ×1000** |
| TN 2004-05 | DES TN, *Season & Crop Report 2004-05*, Table III-B "All Sources" | published | hectares |
| TN 2011-12 | DES TN, *Season & Crop Report 2011-12 (Fasli 1421)*, Table III-B, p.104 | published | hectares |

**Panel: 28 districts × 2 years = 56 rows, 56 accepted, 0 rejected.**

Validation, all passed before acceptance:

| Check | Result |
|---|---|
| `gross − more_than_once == net` | **56 / 56** |
| `gross / net == published intensity` | 36 pass, 20 not applicable |
| AP 2011-12 net area sown, via published cropping intensity | **22 / 22** |
| AP 2011-12 net derivation, via published intensity | **22 / 22** |
| TN OCR rows accepted only after per-district arithmetic validation | enforced |

**A definitional question resolved rather than assumed.** The two TN volumes print different qualifiers on net area — "(excl. wells suppl. other sources)" in 2004-05 versus "(excl. suppl. wells)" in 2011-12. Rather than harmonize, the operational definition was tested against each year's own component tables: net = Σ(all sources) − supplementary wells, **with other sources included**, holds for **29/29** districts in 2004-05 and **16/16** fully-parsed districts in 2011-12, with 12 and 5 discriminating cases respectively. The wording differs; the definition does not.

### One source document is cited rather than stored

`TN_Season_crop_2011-12.pdf` is **171,478,812 bytes (163.53 MB)** and exceeds **GitHub's hard 100 MB per-file limit**, which rejected the push. Rather than recompress it — which would alter the original government publication's bytes and invalidate its checksum — it is **retained locally and specified here in full**, so any reader can re-obtain and verify the identical file:

| Field | Value |
|---|---|
| Publication | *Season and Crop Report, Tamil Nadu 2011-12 (Fasli 1421)*, Directorate of Economics and Statistics, Government of Tamil Nadu |
| Retrieval URL | `https://agritech.tnau.ac.in/pdf/2014/season_crop_11-12.pdf` |
| Retrieved | 2026-09-04 (HTTP 200) |
| Size | 171,478,812 bytes |
| **SHA-256** | `2a41f404a85b4181b02a9b52f2772f1b636d6cec4ca80801b4569052d73b89ec` |
| MD5 | `3b5f2484c7edbd216f13419eb87fb6d2` |
| Table used | TABLE III-B, "TOTAL AREA IRRIGATED", p.104 (of 617) |
| Local path | `data/raw/external/district_irrigation/source_documents/TN_Season_crop_2011-12.pdf` (untracked) |

Reproducibility is preserved by **specification rather than storage**: `ingestion/irrigation_panel_2year.py` reads that path, and the extracted values it produced are committed in `irrigation_panel_2year.csv` along with their per-district identity-validation flags. Every other source document, including the AP 2011-12 publication, **is** committed.

### Exclusions — documented, never imputed

| District | Code | Reason |
|---|---|---|
| Kanniyakumari | `DATA_NOT_AVAILABLE` | Absent from all seven blocks of TN 2011-12 Table III-B (each ends at "30. The Nilgiris"); present on 25+ other pages of the same report, so not OCR failure |
| Ariyalur | `SINGLE_YEAR_ONLY` | Constituted 2007 from Perambalur; absent 2004-05. Perambalur **not** redistributed |
| Coimbatore | `BOUNDARY_NOT_COMPARABLE` | Thiruppur formed 2009 from parts of it — different territory across years. Thiruppur **not** added back |
| Erode | `BOUNDARY_NOT_COMPARABLE` | Same |
| **Hyderabad** | `DATA_NOT_AVAILABLE` | Source prints **"- -"** for 2011-12 net area sown; the ratio is underivable. **Not estimated, not carried forward, not set to zero** |

Nothing was interpolated, imputed, carried forward, redistributed, or substituted with a state average anywhere in this experiment.

## 4. Year alignment (Convention C, approved)

| Period | Irrigation | Yield outcome |
|---|---|---|
| P1 | Fasli 1414 (2004-05) | Kharif 2004 |
| P2 | Fasli 1421 (2011-12) | Kharif 2011 |

Each irrigation observation is paired with the Kharif of **its own agricultural year**. The fasli year runs ~1 July–30 June while the Kharif window is 1 June–30 November, so the Kharif sits 5 of 6 months inside its fasli year. **The offset is identical in both periods and therefore differences out.** Convention A (nearest-observation blocks) was rejected; no yield year outside these two receives an irrigation value.

## 5. Analysis design

```
Δyield_d = α + β·Δpct_net_irrigated_d + γ₁·Δnon_rice_cropped_area_d + γ₂·Δn_crops_grown_d + ε_d
```

| Element | Specification |
|---|---|
| Dependent variable | Δ `final_yield_t_ha` (Kharif 2011 − Kharif 2004) |
| Primary variable | Δ `pct_net_irrigated_to_net_area_sown` (percentage points) |
| District effects | Absorbed by differencing (equivalent to two-way FE on 54 rows) |
| Period effect | The intercept α |
| Inference | HC3 robust (primary) + restricted wild bootstrap, Rademacher, 9,999 reps |
| **N** | **27** |

**Covariates were adjudicated individually, not inherited.** `non_rice_cropped_area_ha` and `n_crops_grown` are time-varying and retained (0 missing at both periods). `elevation_m_mean` and `slope_deg_mean` are **static per district and mechanically absorbed by the district fixed effects** — they were dropped, not carried over from Experiment 4.

## 6. Primary result

| Quantity | Value |
|---|---|
| **β (irrigation)** | **+0.01210 t/ha per percentage point** |
| HC3 standard error | 0.03174 |
| **95% CI** | **[−0.05356, +0.07776]** |
| t | +0.381 |
| **p (HC3)** | **0.7066** |
| **p (wild bootstrap)** | **0.7193** |
| Period effect (intercept) | +0.0060 t/ha |
| R² | 0.3667 |

Sample characteristics: Δ irrigation mean **+7.26 pp** (SD 7.88, range −7.51 to +24.00); Δ yield mean **+0.553 t/ha** (SD 0.944).

## 7. Robustness — all five pre-specified checks, all reported

| # | Check | Result |
|---|---|---|
| **R1** | FD vs two-way FE equivalence | **+0.012100 vs +0.012100 — exactly equivalent.** Implementation validated |
| **R2** | Alternative outcome, P1 = mean(Kharif 2004, 2005) | β **−0.00379**, CI [−0.05645, +0.04887], N = 27 — **sign flips** |
| **R3** | Leave-one-district-out (27 folds) | β range [+0.00193, +0.03904]; **0/27 sign flips**; **0/27 reach p < 0.05** |
| **R4** | AP 2011-12 rounding sensitivity ±500 ha | β +0.01214 / +0.01207 — **negligible** |
| **R5** | Tamil Nadu only (net published directly both years, N = 8) | β +0.00472, CI [−0.13948, +0.14891] — uninformatively wide |

### 7.1 The R2 sign flip — discussed, not buried

Under the primary outcome construction β is **+0.0121**; under the pre-specified alternative (P1 = mean of Kharif 2004 and 2005) it is **−0.0038**. **The point estimate reverses sign** when a single additional yield year is averaged into the first period.

Both estimates are far from significance (primary p = 0.71; alternative CI spans zero comfortably), so this is not a contradiction between two findings — it is a direct demonstration that **the estimate is not determined by the data at this sample size**. A single year of yield noise in one period is enough to move the coefficient across zero. This is corroborating evidence for the INCONCLUSIVE verdict rather than a separate problem, and it means **the direction of the association should not be interpreted at all**.

R3 offers a useful contrast: holding the outcome construction fixed, the sign is stable across all 27 leave-one-out folds. Instability comes from the *outcome definition*, not from any influential district.

## 8. Pre-registered verdict

```
β = +0.01210        95% CI [−0.05356, +0.07776]
p(HC3) = 0.7066     p(wild bootstrap) = 0.7193

CI contains zero:                        YES
CI contains regional-gap anchor 0.0584:  YES
Sign stable across leave-one-district-out: YES

FINAL PRIMARY OUTCOME: INCONCLUSIVE
```

### Why INCONCLUSIVE, and not a negative result

The pre-registered rule classifies a result INCONCLUSIVE when the confidence interval contains **both zero and the effect-size anchor**. It does.

The anchor was fixed before running: the Tamil Nadu regional gap is **+0.8340 t/ha** (Experiment 5, β_A), and the TN vs AP+Telangana difference in net irrigated share in 2004-05 is **53.37 − 39.10 = 14.27 pp**. An effect large enough to account for the whole regional gap would be **β ≈ 0.0584 t/ha per pp**. The interval [−0.0536, +0.0778] contains that value **and** zero.

So the data are simultaneously compatible with *no association at all* and with *an association large enough to explain the entire regional gap*. **The experiment cannot distinguish between them.**

This is a power limitation, not a data-quality failure. The minimum detectable effect at conventional power is roughly **2.8 × SE ≈ 0.089 t/ha per pp — about 1.5× the anchor itself**. With N = 27 and two periods, the design was never capable of resolving an effect of the size that would matter. This risk was stated at Checkpoint 5 as a realistic outcome before any model ran.

## 9. What this experiment does NOT show

1. **It does not show that irrigation has no effect on yield.** An inconclusive interval is not a null finding, and no such claim is made or supported.
2. **It does not test or replicate the Experiment 5 regional-gap question** — that question is structurally inestimable here (§1).
3. **It supports no causal claim in any direction.** A 27-district, two-period observational panel identifies associations only.
4. **It does not license reading the sign of β.** R2 shows the direction reverses under a defensible alternative outcome construction.

## 10. What did work

- The panel is real and internally consistent: **56/56 identity validations**, district sums reconciling with the sources' own published figures.
- A suspected within-TN definitional change was **investigated and disproven** on the sources' own arithmetic, rather than harmonized away.
- **FD ≡ two-way FE exactly**, confirming correct implementation.
- The **AP `'000 Hect.` quantisation is immaterial** (R4), and OCR-derived TN rows behaved consistently with directly-published AP rows.
- Experiment 5's two leakage warnings are **materially addressed**: the 31% future-year exposure is eliminated by same-agricultural-year pairing, and the static district fingerprint is eliminated by differencing (27 of 28 districts show genuine within-district variation).

## 11. Limitations

- **N = 27.** The dominant limitation, and the direct cause of the verdict.
- **Only two irrigation years** — no dynamics, no lags, no ability to model adjustment.
- **AP 2011-12** is published at `'000 Hect.` (quantised to 1,000 ha) and its **net irrigated area is derived** as gross − area-irrigated-more-than-once. The derivation is exact and identity-validated (22/22), but it is a derivation.
- **TN 2011-12 is OCR-derived** from a scanned document; headers are corrupted, and rows were accepted only after passing per-district arithmetic identity checks.
- **The Experiment 5 cross-region AP/TN net-area comparability warning stands.** It is distinct from the within-TN definitional question resolved here, though its force is reduced in this design because a constant cross-region offset differences out.
- Four Tamil Nadu districts and Hyderabad are excluded for documented boundary or availability reasons, leaving 8 of 12 TN study districts.
- **All results are associational, not causal.**

## 12. Conclusion

Experiment 6 successfully built what Experiment 5 lacked — a validated, provenance-complete two-year district irrigation panel with genuine within-district variation — and used it in a design that eliminates the static-attribute and future-year problems Experiment 5 had to declare.

The analysis then returned **INCONCLUSIVE**: at N = 27, the confidence interval is too wide to separate no effect from an effect large enough to explain the whole regional gap. Reporting this as a negative result would overstate what the data support; reporting the positive point estimate would overstate it in the other direction, and the R2 sign flip shows the direction itself is not determined.

The methodological contribution stands independently of the statistical one: the panel, the resolved definitional question, the validated identities and the documented exclusions are reusable, and any future expansion of the irrigation panel — which is the obvious route to the power this experiment lacked — must be treated as a **separate new experiment**.

```
FINAL PRIMARY OUTCOME: INCONCLUSIVE
β = +0.01210 t/ha per pp · 95% CI [−0.05356, +0.07776]
p(HC3) = 0.7066 · p(wild bootstrap) = 0.7193
CI contains both zero and the 0.0584 regional-gap anchor
```
