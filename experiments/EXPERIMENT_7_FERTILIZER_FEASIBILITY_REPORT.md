# Experiment 7 — Fertilizer intensity feasibility investigation

**STATUS: NOT FEASIBLE WITH CURRENT VERIFIED SOURCES**

**Scope of this document.** This is a *feasibility investigation record only*. Checkpoint 2 was
approved on 2026-09-04 with the decision **NOT FEASIBLE**. No modelling dataset was constructed,
no values were merged into any dataset, no derived feature was created, no normalization was
applied, and no regression or predictive model was run. No file under `training/`, `models/`,
`backend/`, or `data/processed/` was modified. Experiments 1–6 are untouched.

This document exists so that the investigation is not repeated and so that the reasons for the
negative decision are auditable.

---

## 0. Question investigated

> Does district-level fertilizer application intensity account for statistical variation in the
> remaining cross-regional agricultural gap between Andhra Pradesh / Telangana and Tamil Nadu?

This was hypothesis **H6-B** in the Experiment 6 hypothesis scorecard, carried forward as
Experiment 7 after Experiment 6's irrigation panel returned INCONCLUSIVE. Fertilizer was ranked
the most scientifically plausible untested input remaining.

**The hypothesis is not refuted by this document.** What is recorded here is that no defensible
*experiment* on it can be constructed from the sources that were verified as obtainable.

---

## 1. Definition comparability — **UNRESOLVED**

The two regions publish fertilizer figures under **different terms, from different agencies, in
different publications**, and **neither publication defines its own term**.

| Evidence sought | Result |
|---|---|
| AP self-definition | **None.** Programmatic search of *Districts at a Glance 2012* for `concept\|definition\|glossar\|explanatory note\|methodolog` returned **zero matches**. No concepts-and-definitions section exists in the publication. |
| AP source attribution | The phrase **"Fertilizers statistics"** only. **No agency is named** for section VIII. |
| TN self-definition | **None.** The same programmatic search of the *Statistical Handbook 2013* returned **zero matches**. |
| TN source attribution | **"Source: Department of Agriculture, Chennai-600 005."** Agency named. |
| Common third official source | **Unreachable.** The Government of India DES *State-wise Consumption of Fertilizers* series was the planned empirical cross-check. `desagri.gov.in` returned **`ECONNREFUSED 164.100.114.118:443`**, consistent with the failures of that host family recorded in the Experiment 5 provenance register. |
| FAI methodology | *Fertiliser Association of India* statistics are behind an access layer; the methodology statement was not publicly retrievable. |
| Web search for an authoritative GoI definition | Did not surface a primary-source definition of either term. |

The AP term is **"DISTRIBUTION OF FERTILIZERS"**. The TN term is **"CONSUMPTION OF CHEMICAL
FERTILIZERS AND PESTICIDES"**. On their plain meaning these are different measurement bases:
distribution is a dispatch/supply quantity, consumption implies use. Whether the two agencies
operationalise them differently is **not established in either direction**.

### 1.1 Structural inference (recorded as inference, not as evidence)

The TN table decomposes its totals by delivery channel — **Private (N 484,601) and
Co-Operative (N 199,958)** — which sum exactly to the state N total of 684,559. A channel
decomposition is characteristic of a **sales/dispatch** measure rather than on-farm application.
This *suggests* the TN "consumption" figure may in practice be nearer to the AP "distribution"
basis than the words imply.

**This is structural inference from table layout, not a source definition, and it is not
treated as resolving the question.** `DEFINITION_WARNING` stands. The two series are
**not demonstrated to be comparable**, and per the standing rule they are neither harmonized nor
assumed equivalent.

**Status assigned: `DEFINITION_NOT_COMPARABLE` (unresolved, not refuted).**

---

## 2. Second matched year — **NOT AVAILABLE**

A second year was sought for each region so that a within-district differenced design of the
Experiment 6 type would be possible.

### 2.1 Andhra Pradesh / Telangana

The undivided-AP district publications are hosted on `ecostat.telangana.gov.in`, which does not
resolve from this environment (recorded in the Experiment 5 provenance register). Retrieval was
therefore attempted through the Internet Archive Wayback Machine, as in Experiment 5.

A full CDX enumeration of `ecostat.telangana.gov.in/PDF/PUBLICATIONS/*` returned **48 archived
PDFs**. Of these:

- **`Districts_at_Glance_2012.pdf` is the only district-level publication present.**
- All others are `Agricultural_at_glance_2013-14`, `2014-15`, `2015-16`,
  `Statistical_Year_Book_2015`, `Statistical_Year_Book_2017`, or `Telangana_at_Glance_2015`
  through `2024` — **every one of them outside the 2000–2012 yield window**.

Direct Wayback probes for `Districts_at_Glance_` editions **2010, 2011, 2013, 2014 and 2015**
returned **no snapshot**.

**Result: exactly one AP/TG year (2011-12) exists within the study window, from any route tested.**

### 2.2 Tamil Nadu

Only `stst_handbook_tn_2013.pdf` is served on the `agritech.tnau.ac.in` host. Probes for the
2011, 2012, 2014, 2015 and 2016 editions returned nothing.

### 2.3 Consequence

**No second matched year is obtainable for either region.** AP is the binding constraint: even
if additional TN years were recovered, a matched panel requires both regions. A within-district
first-difference or two-way fixed-effects design — the design that rescued Experiment 6 from this
exact class of confound — is **impossible**.

**Status assigned: `YEAR_NOT_COVERED` for all study years except 2011-12.**

---

## 3. Tamil Nadu denominator — **RESOLVED, AVAILABLE**

Constructing intensity (fertilizer per hectare) requires a district-level cultivated-area
denominator for each region. The AP denominator was already confirmed and validated during
Experiment 6 (*Districts at a Glance 2012*, p.17, net area sown, identity-validated 22/22).
The TN denominator was the open question.

**Resolved.** It is published in a primary source already held:

> **TN Season and Crop Report 2011-12 (Fasli 1421), TABLE II —
> "CLASSIFICATION OF LAND DURING 2011-12 (in ha.)", p.82**

The table publishes, by district: **Net area sown**, Area sown more than once, and
**Gross area sown**.

**Accounting-identity validation** (net + sown-more-than-once = gross):

| District | Net area sown | Sown >once | Gross | Identity |
|---|---|---|---|---|
| Kancheepuram | 110,872 | 15,770 | 126,642 | ✔ exact |
| Cuddalore | 217,331 | 82,359 | 299,690 | ✔ exact |

Neither `rice_area` nor any target-derived quantity enters this denominator, so it introduces
no target leakage.

**A denominator is therefore available for both regions. The denominator was not the blocker.**

---

## 4. Candidate sources and provenance

All three documents below are **primary official publications**. None was added to the
repository; the 171 MB TN Season & Crop Report in particular is **cited, not stored**, following
the Experiment 6 precedent (GitHub's 100 MB file limit).

| Field | AP / Telangana fertilizer | Tamil Nadu fertilizer | Tamil Nadu denominator |
|---|---|---|---|
| Publication | *Districts at a Glance 2012* | *Statistical Handbook 2013* | *Season and Crop Report 2011-12 (Fasli 1421)* |
| Publishing agency | DES, Government of Andhra Pradesh | DES, Government of Tamil Nadu | DES, Government of Tamil Nadu |
| Table-level attribution | **"Fertilizers statistics" — no agency named** | "Department of Agriculture, Chennai-600 005" | DES Tamil Nadu |
| Retrieval URL | Wayback capture `20190819040958` of `ecostat.telangana.gov.in/PDF/PUBLICATIONS/Districts_at_Glance_2012.pdf` | `https://agritech.tnau.ac.in/pdf/stst_handbook_tn_2013.pdf` | `https://agritech.tnau.ac.in/pdf/2014/season_crop_11-12.pdf` |
| Observation year | 2011-12 | 2011-12 | 2011-12 (Fasli 1421) |
| Exact table | "VIII. DISTRIBUTION OF FERTILIZERS (2011-12) (In Tonnes)" | "4.8 CONSUMPTION OF CHEMICAL FERTILIZERS AND PESTICIDES 2011-12" | "TABLE II CLASSIFICATION OF LAND DURING 2011-12 (in ha.)" |
| Stated units | Tonnes | MT | hectares |
| Districts in table | 23 | 31 | 30 |
| Primary source? | Yes | Yes | Yes |
| File size (bytes) | 291,434 | 1,172,090 | 171,478,812 |
| SHA-256 | `464a3acc1cda543f7f6eba4545569f013c90828c1025f8a9eaab0afbbcb91b5e` | `b845bbcb0edb13e89efc42c1793c5b95dc839b5efec3c70935a6a849891d82a5` | `2a41f404a85b4181b02a9b52f2772f1b636d6cec4ca80801b4569052d73b89ec` |
| Stored in repository? | Yes (already present from Experiment 6) | **No — cited only** | **No — cited only, exceeds GitHub 100 MB limit** |

**State-level totals read from the two fertilizer tables** (recorded for future verification of
any re-extraction):

- **AP (In Tonnes):** N 1,977,287 · K₂O 322,034 · **NPK total 3,342,657**
- **TN (MT):** N 684,559 · P₂O₅ 316,382 · K₂O 263,953 · **NPK total 1,264,894**

---

## 5. District coverage

| Group | Study districts | Fertilizer coverage | Notes |
|---|---|---|---|
| Andhra Pradesh | 10 | **10 / 10** | DIRECT_MATCH; spelling variants Prakasam/Prakasham and Anantapur/Ananthapur |
| Telangana | 10 | **9 / 10** | **Hyderabad printed as `--- ---` → `DATA_NOT_AVAILABLE`**; RENAME_ONLY for Mahbubnagar and Ranga Reddy |
| Tamil Nadu | 12 | **12 / 12** | Includes **Ariyalur and Kanniyakumari**, both of which the Experiment 6 irrigation panel could not cover |
| **Total** | **32** | **31 / 32** | |

Coverage is *better* than the irrigation panel's. **Data availability was not the reason for the
negative decision.**

---

## 6. Boundary compatibility

The design would be a single-year cross-section, so no cross-year boundary reconciliation arises.
Both regions are measured in 2011-12 on their then-current district boundaries.

Coimbatore and Erode — excluded from the Experiment 6 irrigation panel as
`BOUNDARY_NOT_COMPARABLE` because Tiruppur was carved out of them in 2009 — are here measured on
**post-2009 boundaries in both the fertilizer table and the denominator table**, so they would be
internally consistent for this single year. Tiruppur itself is reported as
`* Data Not available for Tiruppur` and is not a study district.

---

## 7. Missingness

| District | Source | Printed value | Status assigned |
|---|---|---|---|
| Hyderabad | AP *Districts at a Glance 2012*, section VIII | `--- ---` | **`DATA_NOT_AVAILABLE`** — explicitly **not** zero |
| Tiruppur | TN *Statistical Handbook 2013*, table 4.8 | `* Data Not available` | `DATA_NOT_AVAILABLE`; not a study district |

No other gaps exist in either fertilizer table across the 32 study districts. No imputation,
interpolation, carry-forward, or state-average substitution was performed or contemplated.

---

## 8. Leakage risk assessment

| Risk | Level | Basis |
|---|---|---|
| Target leakage | **NONE** | Fertilizer tonnage contains no yield component |
| Denominator overlap with target | **NONE** | Net area sown (all crops) is not rice area |
| **District fingerprinting** | **HIGH** | One observed year makes the variable static per district, i.e. a district identifier. This is the failure mode already seen in soil (Experiment 1), `n_rice_seasons` (Experiment 4), and single-year irrigation (Experiment 5) |
| **Region proxy** | **HIGH — decisive** | Two publications, two agencies, two different terms, no definitions. Any systematic AP-vs-TN reporting difference loads **directly and entirely onto the `is_tn` contrast** |
| **Temporal leakage / anachronism** | **SEVERE unless restricted** | The fertilizer observation is 2011-12. Broadcasting it across the 2000–2012 panel would make **~90 % of rows anachronistic**, against 31 % in Experiment 5. The only anachronism-free restriction is a Kharif-2011 cross-section, giving **N ≈ 31 districts** |
| Reverse causality | **PRESENT** | Fertilizer supply responds to past and expected production. A single cross-section offers no identification strategy |

---

## 9. Is fertilizer intensity constructible? — **YES, technically**

Both denominators are district-level, dated 2011-12, officially sourced, definitionally documented
within their own publications, and not derived from the target:

- **AP:** net area sown, *Districts at a Glance 2012*, p.17 (identity-validated 22/22 in Experiment 6)
- **TN:** net area sown, *Season and Crop Report 2011-12*, TABLE II, p.82 (identity-validated, §3 above)

Intensity would additionally neutralise the district-size scaling that afflicts raw tonnages.

**It was not constructed.** Constructibility of the variable is not sufficient for feasibility of
the experiment (see §11).

---

## 10. Is a matched multi-year fertilizer panel feasible? — **NO**

Exactly one year (2011-12) is obtainable per region, and no second AP/TG year exists anywhere in
the 2000–2012 window from any route tested (§2). A within-district differenced or fixed-effects
design of the Experiment 6 type is therefore **impossible**, not merely difficult.

---

## 11. Decision — **NOT FEASIBLE WITH CURRENT VERIFIED SOURCES**

The discovery phase **succeeded**, and more completely than Experiment 6's: 31 of 32 study
districts, both regions, the same observation year, compatible units, and a validated denominator
for each region. The negative decision does not rest on missing data. It rests on how two
remaining defects **interact**:

1. **The definitional mismatch is unresolved and is confounded with the contrast of interest.**
   AP "distribution" (agency unnamed) versus TN "consumption" (Department of Agriculture) differ
   along *exactly* the AP-vs-TN axis the experiment measures. A pure reporting-convention
   difference would be indistinguishable from a regional agronomic effect.

2. **Only one year exists, so the escape route is closed.** Experiment 6 neutralised precisely
   this class of problem — a constant cross-region definitional offset — by differencing within
   districts across two periods. With a single observed year that is not available, and the only
   anachronism-free design left is a **31-district cross-section carrying a static,
   district-identifying regressor**.

Together these reproduce the `n_rice_seasons` failure mode from Experiment 4 — a reporting
convention masquerading as agronomy — except that in Experiment 4 a pre-stated fingerprint screen
detected it, whereas here it would be **undetectable**, because it is confounded with region by
construction. No robustness test available at N ≈ 31 could separate the two.

### 11.1 What this decision does and does not claim

- It **does not** claim that fertilizer has no effect on yield.
- It **does not** refute hypothesis H6-B.
- It **does** state that no defensible cross-region experiment on H6-B can be constructed from
  the 2011-12 data verified as obtainable.

### 11.2 What would change the verdict, in order of decisiveness

1. **An official methodology statement** establishing that AP "distribution" and TN "consumption"
   share a measurement basis. The GoI DES route (`desagri.gov.in`) was *unreachable, not
   exhausted*; FAI *Fertiliser Statistics* is the other candidate.
2. **A second observed year for both regions.** TN publishes annual *District Statistical
   Handbooks* which remain unexplored; AP/TG is the harder constraint, since only one district-level
   edition survives in the archive.
3. **Reframing to a within-region question** that does not rest on the AP/TN contrast — though the
   single-year constraint forecloses this too.

Per the Checkpoint 2 approval, **no further fertilizer source discovery is authorized.** Any such
search must be commissioned as a separate, explicitly approved source-discovery task, and any
resulting experiment must be treated as a new experiment.

---

## 12. Actions taken and not taken

**Taken:** source discovery; reachability probes; Wayback CDX enumeration; structural reading of
the three candidate tables; accounting-identity validation of the TN denominator; district-name
coverage matching; this document and its machine-readable companion
`experiments/experiment7_feasibility.json`.

**Not taken:** no modelling dataset created; no merge; no normalization; no derived feature; no
regression; no predictive model; no figure; no change to
`data/processed/district_multimodal_examples.csv`; no change to `training/`, `models/`,
`backend/`, or `training/dataset.py`; no change to any Experiment 1–6 report, dataset, result file,
or figure; no large source file added to the repository.

---

*Checkpoint 2 approved 2026-09-04. Decision: NOT FEASIBLE. Recorded for provenance; no analysis performed.*
