# Experiment 9 — Measurement-validation pre-specification

**Scope: instrument validation only.** This document governs the comparison of two independent
temperature products and the feasibility screening of candidate temperature constructs. It does
**not** specify a yield experiment, and no yield variable is loaded, joined, correlated or
modelled under it.

Written before the daily-resolution comparison and before any construct screening.

---

## 0. Disclosure — what was already seen

This specification is **not fully blind, and must not be presented as such.**

During the preceding authorised feasibility phase, a **monthly-resolution** ERA5-vs-IMD maximum
temperature comparison was already computed and reported:

```
within-district-month Pearson r:   Andhra Pradesh 0.896 | Telangana 0.912 | Tamil Nadu 0.775
mean absolute difference:          AP 1.55 C | TG 2.00 C | TN 1.77 C
mean signed bias (ERA5 - IMD):     AP -1.52 C | TG -2.00 C | TN -1.16 C
```

Consequences, stated precisely:

- The **monthly** comparison is already observed. Re-reporting it below is a restatement, not a
  new blind result, and the regional-evenness rule in §3 cannot be treated as having been set
  before those particular numbers were seen.
- The **daily-resolution** comparison specified in §2 has **not** been computed. Daily ERA5
  `temperature_2m_max` has never been pulled in this project. That comparison is genuinely
  pre-specified by this document.
- The **construct screens** in §4 have **not** been computed on Tmax. The `t_sd_daily`,
  `t_range_season` and `t_p95` figures reported earlier were derived from daily **mean**
  temperature, a different variable. No Tmax-derived construct has been screened.
- The threshold in §3 is **inherited from Experiment 8's already-published standard**, not
  invented for this comparison. It is stated below in the form Experiment 8 used.

---

## 1. Measurement definitions

### ERA5-Land (candidate instrument)

| Property | Value |
|---|---|
| Collection | `ECMWF/ERA5_LAND/DAILY_AGGR` |
| Band | `temperature_2m_max` |
| Native units | Kelvin → converted to °C by subtracting 273.15 |
| Spatial reduction | Mean over the district polygon at 11,132 m (ERA5-Land native ~0.1°) |
| Polygons | The **same** geometries used by Experiment 8, from `data/metadata/boundary_sources/district_polygons_ee/` |
| Years | 2000–2012 |
| Seasonal window | **1 June – 30 November** — the Kharif window used by Experiment 8, unchanged |

### IMD (independent reference)

| Property | Value |
|---|---|
| Institution | India Meteorological Department, Pune |
| Product | Gridded daily maximum temperature, **1.0° × 1.0°** binary |
| Source page | `https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html` |
| Retrieval | HTTP POST `maxtemp=<year>` to `https://www.imdpune.gov.in/cmpg/Griddata/maxtemp.php` |
| Grid | float32 little-endian, (days, 31 lat, 31 lon); lat 7.5–37.5, lon 67.5–97.5 at 1.0° |
| Missing sentinel | **99.9** — note this differs from the rainfall product's −999.0 and must never be read as data |
| Years | 2000–2012 |
| Seasonal window | 1 June – 30 November, identical to ERA5 |

### Aggregation methodology (fixed here, not after results)

IMD cells are assigned to a district by **cell-centre-inside-polygon**, the same rule used for
IMD rainfall in Experiment 8. Where a district contains no 1° cell centre, the **nearest cell to
the district centroid** is used and the district is flagged `CELL_FALLBACK_NEAREST`. The district
value is the unweighted mean over its assigned cells. Missing-flagged cells are dropped, never
zero-filled.

**Known resolution constraint, recorded in advance.** At 1.0°, 12 of the 31 districts contain no
cell centre, the 31 districts resolve to only **24 distinct cells**, and **14 districts (45 %)
share a cell** with a neighbour. IMD Tmax is therefore admissible as a **validation reference
only** and is explicitly **not** a candidate district-level predictor. The sharing is close to
even across regions (AP 10→8, TN 12→9, TG 9→7), so it is not expected to bias the regional
comparison, but any regional difference in agreement must be re-tested on the subset of districts
resolving to exactly one cell before being attributed to the region.

---

## 2. Comparison metrics

Computed at **daily** resolution and aggregated to district-year, for each region — Andhra
Pradesh, Telangana, Tamil Nadu — and overall:

1. **Within-district Pearson correlation** (district means removed, so the statistic reflects
   year-to-year co-movement rather than cross-district level differences) — the primary metric,
   matching Experiment 8's rainfall validation
2. **Mean absolute difference** (°C)
3. **Mean signed difference / bias**, ERA5 − IMD (°C)
4. **Number of district-years**
5. **Number of districts**
6. **Number of years**

Reported additionally: per-district agreement, and agreement by month, to locate any
disagreement rather than only quantify it.

---

## 3. Regional-evenness rule — fixed before the daily comparison

The standard is **inherited verbatim from Experiment 8**, not constructed for this comparison:

> A materially weaker independent-product agreement in one region, especially if that region is
> also the source of any subsequent apparent effect, constitutes a **measurement-validity
> warning**.

Applied here, a warning is raised when **both** hold:

- **(a)** one region's within-district correlation is materially below the others, and
- **(b)** the shortfall survives the single-cell re-test described in §1.

For calibration against a case already adjudicated, Experiment 8's rainfall result — TN 0.446
against AP 0.770 and TG 0.751, a TN/AP ratio of **0.58** — was judged to warrant a **CONFIRMED**
measurement limitation. That precedent is the reference point; no new numeric cutoff is invented
here.

**This validation cannot, and will not, be used to declare any scientific effect.** It can
establish only whether the instrument is fit to be used, never what it would show about yield.

---

## 4. Construct feasibility screens

Candidate constructs, computed from **daily ERA5 Tmax only** — the daily-mean-temperature
versions of the two count constructs were rejected in the preceding phase and are **not revived**:

| Construct | Definition | Units |
|---|---|---|
| `t_sd_daily_tmax` | Standard deviation of daily Tmax across the Kharif window | °C |
| `t_range_season_tmax` | Max minus min of daily Tmax across the window | °C |
| `t_p95_tmax` | 95th percentile of daily Tmax across the window | °C |
| `tdays_gt32_tmax` | Count of days with **Tmax** > 32 °C | days |
| `tdays_gt30_tmax` | Count of days with **Tmax** > 30 °C | days |

For each, report: definition, units, available district-years, missingness, region coverage,
denominator, observation count, within-district **ICC**, **KS** statistic (TN vs AP+TG),
**standardized mean difference**, and **zero-rate** where the construct is a count.

### Rejection rules, fixed in advance

- **ICC > 0.90** ⇒ district fingerprint ⇒ rejected (the rule that disqualified seasonal mean
  temperature at ICC 0.939)
- **KS ≥ 0.95 or |SMD| ≥ 3** ⇒ region proxy ⇒ rejected for cross-region use
- **Region-correlated zero-inflation** ⇒ rejected. This is the defect that disqualified the
  daily-mean count constructs (TN 69.4 % zero against TG 25.9 %, with 6 districts always zero).
  A count construct is rejected if its zero-rate differs materially across regions, or if any
  district is always zero and thereby contributes no within-district variation.

No construct advances on ICC, KS or SMD alone. A single binding defect rejects it regardless of
how the other screens read.

---

## 5. What this document does not authorise

No yield variable may be loaded or joined. No predictor–yield relationship may be estimated. No
Experiment 9 modelling dataset may be constructed. No Experiment 1–8 artefact may be modified,
rerun or reinterpreted. Nothing may be committed or pushed under this specification.

---

*Written before the daily ERA5 Tmax pull, before the daily comparison, and before any Tmax
construct screen. Monthly-resolution disclosure recorded in §0.*
