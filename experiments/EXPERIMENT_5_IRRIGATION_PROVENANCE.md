# Experiment 5 — Irrigation source register and provenance

**Checkpoint 2 record. Source discovery and assessment only.**

No data was downloaded into any dataset, no file was merged, no derived feature was created, no model was run. Assessment consisted of reachability probes (DNS + HTTP HEAD), published metadata, and — for one document that a fetch tool cached automatically — a *structural readability probe only* (page count, presence of the word "irrigation", title block). No values were extracted.

---

## 1. Reachability from this environment (measured, 2026-09-04)

| Host | DNS | HTTP | Note |
|---|---|---|---|
| `agritech.tnau.ac.in` | 14.139.187.9 | **200** (PDF, 5.69 MB) | TN Season & Crop Report 2009-10 |
| `des.tn.gov.in` | 103.59.64.31 | **200** | TN DES portal |
| `www.ndl.gov.in` | 203.110.243.184 | resolves | National Digital Library |
| `jalshakti-dowr.gov.in` | 164.100.11.197 | **200** | Ministry of Jal Shakti |
| `vdsa.icrisat.org` | 111.93.13.165 | **200** | ICRISAT |
| `data.icrisat.org` | 111.93.13.169 | blocked by fetch policy | — |
| `www.indiastat.com` | 180.179.212.100 | **200** | Commercial |
| **`ecostat.telangana.gov.in`** | **DNS FAIL** | — | **Hosts the undivided-AP reports** |
| `ecostat.ap.gov.in` | **DNS FAIL** | — | — |
| `www.ecostat.ap.gov.in` | **DNS FAIL** | — | — |
| `apecostat.ap.nic.in` | **DNS FAIL** | — | — |
| `desap.cgg.gov.in` | **DNS FAIL** | — | — |
| `data.desagri.gov.in` | resolves | ConnectionError | national DES |
| `desagri.gov.in` | resolves | ConnectTimeout | — |
| `aps.dac.gov.in` | resolves | ConnectTimeout | — |
| `indiawris.gov.in` | resolves | ConnectTimeout | — |
| `micensus.gov.in` | **DNS FAIL** | — | Minor Irrigation Census portal |

Other Indian government hosts resolve normally from this machine, so the AP/Telangana failures are specific to those hosts rather than a general network fault.

## 2. Source assessments

### S1 — Tamil Nadu DES, Season and Crop Report — **POSSIBLY_ACCEPTABLE**

- **Organization:** Directorate of Economics and Statistics, Government of Tamil Nadu
- **Report:** *Season and Crop Report of Tamil Nadu*
- **Geographic level:** District
- **Variables (confirmed from the 2024-25 table index, Part III Section III):** III.A number and sources of irrigation; **III.B area irrigated by different sources of irrigation**; III.C percentage contribution by source; III.D masonry/non-masonry wells and bore wells; III.E well classification
- **Time definition (verbatim from the document):** **Fasli year.** The 2009-10 edition is titled "SEASON AND CROP REPORT TAMILNADU 2009-10 (Fasli 1419)"; NDLI lists "2004-05: fasli year – 1414". So Fasli 1419 = 2009-10 and Fasli 1414 = 2004-05. **The exact month span of the fasli year is NOT yet confirmed from a primary document** and is therefore recorded as unverified. Per Decision 2 no mapping is assumed.
- **Access status:** Official DES portal archive **starts at 2014-15** — it does **not** cover 2000–2012. One in-period volume (2009-10, Fasli 1419) is reachable via `agritech.tnau.ac.in`; NDLI indexes 2002-03, 2004-05 and 2005-06.
- **Readability:** the 2009-10 PDF is **352 pages and machine-extractable** (title block read cleanly; 19 of the first 60 pages mention irrigation). Not a scanned image.
- **Suitability:** Primary, official, district-level, in-period, extractable. The constraint is **year availability**, not readability.

### S2 — Andhra Pradesh DES, Season and Crop Report (undivided AP) — **ACCESS_FAILED**

- **Organization:** Directorate of Economics and Statistics, Government of Andhra Pradesh (volumes now hosted by Telangana's DES)
- **Documents indexed:** *Season and Crop Report Andhra Pradesh 2006-2007/1416 Fasli*; *2004-2005/1414 Fasli*; *Agricultural Statistics at a Glance 2005-06*
- **Geographic level:** District, **undivided Andhra Pradesh** — i.e. it covers both present-day AP and present-day Telangana study districts, which is exactly what this experiment needs
- **Variables:** district-wise area irrigated by source. Search snippets quote district canal-irrigated areas for **Guntur (3.01 lakh ha)** and **Krishna (2.24 lakh ha)** — both are study districts. Units appear as **lakh hectares** in narrative text; table units unverified.
- **Time definition:** Fasli year (1416 = 2006-07, 1414 = 2004-05). Month span unverified.
- **Access status:** **`ecostat.telangana.gov.in` does not resolve from this environment** (DNS failure), and every alternate AP/Telangana statistics host tested also fails. The documents are indexed by search engines but are **not retrievable here**.
- **Suitability:** Would be the ideal AP/TG source. Currently unobtainable.

### S3 — ICRISAT District Level Database — **CLASSIFIED SEPARATELY (barred from primary analysis)**

- **Two variants exist**, and the distinction matters for your Decision 1:
  - **Apportioned:** data from districts formed after 1966 is *given back to parent districts* using **1966 district boundaries**. This is an explicit redistribution of historical values. **Barred from the primary analysis** by Decision 1.
  - **Unapportioned:** uses **current district boundaries, up to 2015-16**, without that redistribution.
- **Redistribution methodology (documented):** "A methodology was devised for apportioning the data of newly formed districts back to its parent district using 1966 district boundaries to ensure continuity in the database for time series analysis."
- **Documentation:** `vdsa.icrisat.org/Include/document/all-apportioned-web-document.pdf` (host reachable, 200)
- **Variables:** includes irrigated area and source-wise irrigation among 1,030 variables
- **Caveat recorded from ICRISAT's own documentation:** for some crops, crop-wise irrigated area **exceeds** the area under the crop, because values come from different sources. Also, some variables were infilled using satellite-derived estimates — which would be a modelled, not observed, value.
- **Status:** The apportioned variant is barred. **Whether the *unapportioned* variant is admissible is an open question requiring your decision** — it is not itself redistributed, so Decision 1 does not automatically exclude it, but its infilling caveat needs verifying before use.

### S4 — Minor Irrigation Census (Ministry of Jal Shakti) — **POSSIBLY_ACCEPTABLE**

- **Organization:** Ministry of Jal Shakti, Government of India
- **Geographic level:** District, all-India (so it covers **both** study regions — the only reachable candidate that does)
- **Time definition:** **Census reference years only** — relevant rounds fall near 2000-01 and 2006-07, both inside the target period. Not an annual series.
- **Access status:** `micensus.gov.in` **DNS FAIL**; parent `jalshakti-dowr.gov.in` reachable (200). Exact document location not yet established.
- **Suitability:** Strong on coverage and independence; weak on temporal density. **No interpolation between census years is permitted**, so it would supply at most ~2 observation years per district.

### S5 — `data.gov.in` — **REJECTED (already exhausted in Experiment 4)**

Experiment 4 scanned 25,000 resources: 13 irrigation datasets, **12 state-level** (barred by the no-state-substitution rule). The single district-level candidate (`9678fb5e`, *Source-wise net Area Irrigated by Districts 2016-17*) returned **HTTP 502 on three attempts** and covers **2016-17** — outside the target period regardless. Rejected on both grounds.

### S6 — `dataful.in` / `indiastat.com` — **REJECTED as primary**

Commercial aggregators that redistribute official data. `indiastat.com` reachable (200) but paywalled. These are secondary redistributors, not primary sources, and their provenance chain to the original DES tables cannot be verified from the public pages. Not admissible as a primary scientific source. Could only ever serve as a cross-check, and only with explicit approval.

### S7 — National Digital Library of India — **POSSIBLY_ACCEPTABLE (lead, unverified)**

Indexes *Season and crop report of Tamil Nadu 2004-05: fasli year – 1414* and reportedly 2002-03 and 2005-06. Host resolves. Whether full PDFs are downloadable without authentication is **not yet verified**. Potentially the route to additional in-period Tamil Nadu years.

## 2a. Checkpoint 2 rulings applied

- **Option 1 approved:** attempt AP/TG retrieval through alternative authoritative routes. Not yet INCONCLUSIVE — the barrier is access, not proven non-existence.
- **ICRISAT unapportioned:** `POSSIBLY_ACCEPTABLE — VALIDATION/SENSITIVITY ONLY PENDING VARIABLE-LEVEL PROVENANCE AUDIT`. Not used in the primary analysis unless each irrigation value is verified as genuinely observed (not satellite/model-infilled), district-level, historically appropriate, clearly defined, and not redistributed. **No ICRISAT data was retrieved at Checkpoint 3.**

---

# Checkpoint 3 — raw retrieval record

Retrieval route used: **Internet Archive Wayback Machine**, which preserves the *original official publication* byte-for-byte. The publication identity below is the government publication; the Wayback URL is only the retrieval path and is recorded separately so the two are never conflated. Nothing was normalized, merged, interpolated, imputed, aligned or modelled.

Stored under `data/raw/external/district_irrigation/source_documents/`.

## R1 — Andhra Pradesh (undivided), 2004-05 — **RETRIEVED AND VERIFIED**

| Field | Value |
|---|---|
| Publication | *Season and Crop Report, Andhra Pradesh, 2004-2005 / 1414 Fasli* |
| Publisher (from title page) | Directorate of Economics and Statistics, Government of Andhra Pradesh, Hyderabad – 500 004 |
| Retrieval route | Wayback snapshot `20190819070027` of `ecostat.telangana.gov.in/PDF/PUBLICATIONS/Season_crop_2004-05.pdf` |
| Local file | `AP_Season_crop_2004-05_fasli1414.pdf` |
| Size / integrity | 7,406,857 bytes; SHA-256 begins `b0a734eb6a263826`; valid `%PDF-` header |
| Pages | 412; machine-extractable (not a scan) |
| Reporting period | Fasli 1414 = 2004-05. **Month span still UNVERIFIED; no mapping performed.** |
| Geographic level | **District**, undivided Andhra Pradesh (23 districts) |
| Key table | **DETAILED TABLE III-B — "Area Irrigated by Different Sources in Andhra Pradesh by Districts 2004-2005"**, pp. 156–165+ |
| Unit | **"(Area in Hectares)"** — stated explicitly in the table header, not inferred |
| Source categories | Tanks (very large / large / small), Major/Medium/Minor project canals, Other minor & petty sources, Public & private lift irrigation, Tube wells, Open wells, etc. — kept as published |
| Study-district coverage | **20 of 20** AP + Telangana study districts present |
| Historical names observed | `PRAKASHAM`, `ANANTHAPUR`, `MAHABOOBNAGAR`, `RANGAREDDY`, `VISAKAHAPATNAM` (source spellings; **no mapping applied — that is Checkpoint 4**) |
| Also present | State-level Summary Table B1 (sourcewise net area irrigated 2000-01→2004-05). **State-level; not usable as district data.** |

## R2 — Tamil Nadu, 2004-05 — **RETRIEVED, BUT DEFINITIONALLY LIMITED**

| Field | Value |
|---|---|
| Publication | *Season and Crop Report of Tamil Nadu 2004-05* |
| Publisher | Department of Economics and Statistics, Government of Tamil Nadu |
| Retrieval route | Wayback snapshots of `tn.gov.in/crop/archives/year2004_05/` |
| Local files | `TN_2004-05_SourcesofIrrigation.htm` (17,854 B, sha `dd13584fa1b1`), `TN_2004-05_AreaIrrigated.htm` (5,687 B), `TN_2004-05_districttables.htm` (8,031 B) |
| Geographic level | District table present |
| **What the district table actually contains** | Columns `DISTRICT | CANALS | TANKS | WELLS | OTHERS`, each as **`% to the State`** and **`% to all Sources in the district`** — i.e. **percentages only** |
| **What it does NOT contain** | Absolute net or gross irrigated area in hectares, by district |
| State-level figures present | Net area irrigated 2004-05 = 2,637,198 ha (state); 51.7% of net area sown. **State-level; not usable as district data.** |
| Missing table | `Part3_3b.htm` — "Area irrigated by different source of irrigation" (the absolute-hectare district table, the direct counterpart to AP's III-B) is listed in the report's own index but was **never captured by the Wayback Machine** (`404`/absent from CDX). Status: `SOURCE_ACCESS_FAILED`. |

## R3 — Tamil Nadu, 2009-10 — **AVAILABLE (live host), NOT MATCHED IN YEAR**

*Season and Crop Report Tamil Nadu 2009-10 (Fasli 1419)*, DES Tamil Nadu; `agritech.tnau.ac.in`, HTTP 200, 5,693,446 bytes, 352 pages, machine-extractable; 19 of first 60 pages mention irrigation. Contains district tables III.A–III.E including "area irrigated by different sources of irrigation". **No corresponding AP/TG 2009-10 volume is retrievable**, so this year has no cross-region counterpart.

Additional TN volumes located but not retrieved: 2011-12, 2012-13 (`agritech.tnau.ac.in`); DES portal archive begins 2014-15.

## Retrieval attempts that failed

| Target | Outcome |
|---|---|
| `ecostat.telangana.gov.in` (all AP/TG DES volumes, direct) | `SOURCE_ACCESS_FAILED` — DNS failure from this environment |
| AP *Season and Crop Report 2006-07* via Wayback | `NO SNAPSHOT` |
| AP *Agricultural Statistics at a Glance 2005-06* via Wayback | `NO SNAPSHOT` |
| TN `Part3_3b.htm` (absolute district irrigation, 2004-05) | `SOURCE_ACCESS_FAILED` — never archived |
| `micensus.gov.in` (Minor Irrigation Census) | DNS failure; parent `jalshakti-dowr.gov.in` reachable but document location not established |
| `data.desagri.gov.in`, `indiawris.gov.in`, `aps.dac.gov.in` | Connect timeout |

Wayback holds only **one** in-period AP/TG statistical volume (2004-05). Other archived ecostat publications are 2013-14 or later, outside the target period.

---

# Checkpoint 3 (continued) — Minor Irrigation Census assessment (Option 3)

Approved instruction: retrieve and inspect the MI Census through reachable authoritative Jal Shakti / Government routes for **both** regions; do not yet make it the primary source; report failure rather than substitute state-level data.

## Access

`micensus.gov.in` and `minorirrigation.gov.in` fail DNS; `mowr.gov.in` and the file host `164.100.229.38` connect-timeout; `jalshakti-dowr.gov.in` is reachable but its irrigation-census page returns **HTTP 403**. Retrieval therefore again used the Wayback Machine, which preserves the original Government of India publications.

## Documents retrieved

| Item | Detail |
|---|---|
| **4th MI Census, reference year 2006-07** | *Report of the 4th Census of Minor Irrigation Schemes*, Ministry of Water Resources / Jal Shakti. Wayback snapshot `20230307043233` of `164.100.229.38/sites/default/files/4thmicensusreport.pdf`. **7,303,328 bytes, SHA-256 `2c3f770cce0f`, 431 pages, machine-extractable.** |
| **3rd MI Census, reference year 2000-01** | *Report on 3rd Census of Minor Irrigation Schemes*. Wayback snapshot `20231205020931`. Download terminated at exactly **1,048,576 bytes** and the file fails to open (`Unexpected EOF`). Status: **`SOURCE_UNREADABLE` (truncated retrieval)**. |

## What the 4th MI Census actually contains — measured, not assumed

| Check | Result |
|---|---|
| Pages containing the word "District" | 33 of 431 |
| Pages carrying ≥3 Tamil Nadu study districts (i.e. a district table) | **0** |
| Pages carrying ≥3 AP/Telangana study districts | **0** |
| Pages containing *any* single TN study-district name | 4 |
| Pages containing *any* single AP/TG study-district name | 9 |
| Pages with systematic state-level tables | 23 |

The only district-level content is **Appendix-II, Table A-1: "Districts with more than 1 lakh MI schemes"** — a **threshold-filtered, partial** list (complete district coverage is absent by construction), and its variable is **NUMBER OF SCHEMES**, a count. The remaining district references are narrative asides ("Salem and Coimbatore in Tamil Nadu … are among …").

The portal page titled **"State Wise Reports"** was enumerated in full: it links only the six **national** census reports plus schedules and instruction manuals. **No per-state or per-district volume is published there.**

## Variable definitions (from the census methodology)

The MI Census enumerates **schemes**, not areas: dug wells, shallow/medium/deep tube wells, surface flow and surface lift schemes, together with **irrigation potential created (IPC)** and **potential utilised**, ownership, holding size, lifting devices and energy source.

Two definitional consequences, both material:

1. **IPC / potential utilised is not net or gross irrigated area.** It is a design-capacity concept, not an area actually irrigated in a given season. It is therefore **not** the pre-registered primary variable and is not interchangeable with it.
2. **The census covers only schemes with Culturable Command Area ≤ 2,000 ha** — minor irrigation by definition. It **systematically excludes major and medium canal systems.** That exclusion removes precisely the irrigation most likely to matter for this experiment: Tamil Nadu's Cauvery-delta districts and Andhra Pradesh's Krishna/Godavari-delta districts are served by major projects. Using MI Census as a proxy for total irrigation would therefore be biased in a way that is correlated with the very regional contrast under study.

## Observed vs estimated

Values are enumerated by field census (observed), not modelled — a genuine strength. That strength does not overcome the coverage and definitional failures above.

## Verdict on Option 3

**The Minor Irrigation Census cannot supply scientifically comparable district-level irrigation coverage for both regions**, through any route reachable here:

- district-level irrigated-area data: **absent** for both regions;
- district coverage: **partial and threshold-filtered**, not systematic;
- variables: **scheme counts and potential**, not net/gross irrigated area;
- scope: **excludes major/medium irrigation**, biasing against delta districts in both regions;
- 2000-01 round: **unreadable/truncated** on retrieval.

Reported as a failure. **No state-level value was substituted, no design change was made, and no interpolation was performed.**

---

# Checkpoint 3 (final) — Tamil Nadu 2004-05 absolute-area retrieval (Option 2)

**Outcome: SUCCESS.** The missing table was located at a different archive path. `Part3_3b.htm` was never captured under `/crop/archives/year2004_05/`, but the **top-level** `/crop/Part3_3b.htm` has **25 Wayback captures**, and the January–February 2007 captures hold the 2004-05 edition (the site served the then-current report at the top level, matching the 2004-05 label on the contemporaneous `ChSourceNetArea.htm` capture).

## R4 — Tamil Nadu 2004-05, Table III-B — **RETRIEVED AND VERIFIED**

| Field | Value |
|---|---|
| Publication | *Season and Crop Report 2004-05*, Government of Tamil Nadu, Department of Economics and Statistics |
| Table | **TABLE III-B — "Area Irrigated by Different Sources of Irrigation 04-05"** |
| Retrieval route | Wayback snapshot `20070108113320` of `http://www.tn.gov.in/crop/Part3_3b.htm` |
| Local file | `TN_2004-05_TableIIIB_AreaIrrigatedBySource_hectares.htm` |
| Size / integrity | 42,573 bytes; SHA-256 begins `ffd8cd9cb009` |
| **Unit** | **"(in ha.)" — stated explicitly in the table header** |
| Variables | Per source: **GROSS AREA** (Govt / Private / Total), **NET AREA** (Govt / Private / Total), **Irrigation Intensity** |
| Source blocks | 1) CANALS · 2) TANKS · 3) WELLS (SOLE IRRIGATION) · 4) SUPPLEMENTARY IRRIGATION (all types of wells) · 6) OTHER SOURCES (Spring Channels etc.) |
| Districts | **30** |
| Study-district coverage | **11 of 12** |

## R5 — Tamil Nadu 2005-06, Table III-B — retrieved opportunistically

Same table for 2005-06 (`20080501154844`), 45,881 bytes, SHA-256 `6b38f3f9a5f6`, also "(in ha.)". Retained; **not** part of the matched-year design unless a corresponding AP 2005-06 volume is ever obtained.

## Comparability against AP 2004-05 — verified at the table level

AP **DETAILED TABLE III-B (Concld.)**, p.170, "(Area in Hectares)", gives per district:

- **Net area irrigated**
- % of net area irrigated **to net area sown**
- Area irrigated more than once
- **Gross area irrigated**
- % of gross irrigated area to total cropped area

| Property | AP / Telangana | Tamil Nadu | Comparable? |
|---|---|---|---|
| Publication type | DES *Season and Crop Report* | DES *Season and Crop Report* | Yes |
| Year / fasli | 2004-05 / 1414 | 2004-05 / 1414 | **Yes — matched** |
| Geographic level | District | District | Yes |
| Unit | Hectares (stated) | Hectares (stated) | Yes |
| **Net area irrigated** | Present | Present | **Yes** |
| **Gross area irrigated** | Present | Present | **Yes** |
| Irrigated fraction | Published directly (% to net area sown) | Derivable / intensity published | Needs a Checkpoint 7 decision |
| **Source-composition categories** | Major / medium / minor project canals; tanks by size; lift; tube/open wells | Canals; tanks; wells (sole); supplementary; other | **NO — taxonomies differ** |

**Net and gross irrigated area are comparable across the two publications. The source-composition breakdowns are NOT** — the two DES offices use different source taxonomies, so canal/tank/well shares must not be compared category-by-category without an explicit, approved reconciliation.

## Boundary and naming issues found (for Checkpoint 4 — nothing mapped yet)

| Study district | Situation | Provisional status |
|---|---|---|
| **Ariyalur** (TN) | **Absent from the 2004-05 source.** Ariyalur was carved out of **Perambalur** in 2007, so it did not exist in the reporting year. | **Do not redistribute Perambalur's values.** Candidate `UNMAPPABLE` / `YEAR_NOT_COVERED` |
| **Kanniyakumari** (TN) | Source spells it **"Kanyakumari"** | Candidate `RENAMED`/spelling variant |
| AP/TG study districts | Source spellings `PRAKASHAM`, `ANANTHAPUR`, `MAHABOOBNAGAR`, `RANGAREDDY`, `VISAKAHAPATNAM` | Candidate spelling variants |

## Study-district coverage summary (2004-05, matched year)

| Region | Study districts | Present in source | Missing |
|---|---|---|---|
| Andhra Pradesh | 10 | **10** | — |
| Telangana (then undivided AP) | 10 | **10** | — |
| Tamil Nadu | 12 | **11** | Ariyalur (did not exist in 2004-05) |
| **Total** | **32** | **31** | **1** |

---

# Checkpoint 4 — district harmonization

Mapping table: `data/raw/external/district_irrigation/district_mapping_table.csv`, generated by `ingestion/irrigation_district_mapping.py`. Every row is declared explicitly in source; **no fuzzy matching is used anywhere**, because a fuzzy matcher will also "successfully" match two genuinely different districts.

Nothing was merged, no derived feature was created, no year was aligned, no statistic was computed.

## Counts

| Mapping type | Count |
|---|---|
| EXACT | 26 |
| RENAMED | 5 |
| SPLIT | 0 |
| MERGED | 0 |
| AMBIGUOUS | 0 |
| **UNMAPPABLE** | **1** |
| **Total** | **32** |

`SPLIT` and `MERGED` are deliberately unused: neither is applied to move a value. Where a split leaves a study district absent from the source year, the row is `UNMAPPABLE` instead.

## Coverage by region

| Region | Study districts | Mapped | Unmappable |
|---|---|---|---|
| Andhra Pradesh | 10 | **10** | 0 |
| Telangana | 10 | **10** | 0 |
| Tamil Nadu | 12 | **11** | 1 |
| **Total** | **32** | **31** | **1** |

## The five RENAMED cases (spelling/transliteration only, no boundary change, no value moved)

| HarvestWise | Source as printed | Region |
|---|---|---|
| KANNIYAKUMARI | Kanyakumari | Tamil Nadu |
| ANANTAPUR | ANANTHAPUR | Andhra Pradesh |
| PRAKASAM | PRAKASHAM | Andhra Pradesh |
| MAHBUBNAGAR | MAHABOOBNAGAR | Telangana |
| RANGAREDDI | RANGAREDDY | Telangana |

## The one UNMAPPABLE case

**ARIYALUR (Tamil Nadu) — `UNMAPPABLE_YEAR_NOT_COVERED`.** Ariyalur was constituted in **2007** from Perambalur and therefore does not exist in the 2004-05 source. Perambalur's values were **not** assigned, split, estimated or copied to it.

Coherence check supporting this classification: the HarvestWise rows that would need an Ariyalur irrigation value are dated **2009, 2010, 2011, 2012** — all after the district's 2007 creation, exactly as expected. **4 of 382** matched-condition rows are affected; **378 remain**, comprising Tamil Nadu 139, Andhra Pradesh 130, Telangana 109.

## Telangana state attribution (documented, not a remapping)

The ten Telangana study districts are reported in the source under **"Andhra Pradesh (undivided)"**, because Telangana was formed in 2014. In 2004-05 these districts existed under the same names with the same boundaries. The mapping table records `source_state_as_printed` separately from `harvestwise_region` so this is visible rather than silently reconciled. **This is a state-attribution difference, not a boundary change and not a redistribution.**

## Validation performed

Every one of the 31 non-UNMAPPABLE `source_district_name` values was checked against the district-name list actually extracted from the corresponding source table. **Result: 0 mismatches** — no mapping points at a name the source does not contain.

## Boundary caveat recorded for later checkpoints (not resolved here)

**Tiruppur district was formed in 2009** from parts of Coimbatore and Erode. A 2004-05 irrigation figure for Coimbatore or Erode therefore describes a **larger** district than the post-2009 Coimbatore/Erode appearing in HarvestWise yield rows for 2009–2012. The mapping is still one-to-one by identity, but applying a single 2004-05 value across 2000–2012 crosses this boundary change. Flagged as `OBSERVED_WITH_BOUNDARY_CAVEAT` in the table; the decision about how (or whether) a single-year value may be applied across the panel belongs to **Checkpoint 7**, not here.

## 3. Time definitions recorded (Decision 2 — nothing mapped)

| Source | Stated time unit | Month span | Mapping to Kharif 2000–2012 |
|---|---|---|---|
| TN Season & Crop Report | Fasli year (1419 = 2009-10) | **UNVERIFIED** | **NOT PERFORMED** |
| AP Season & Crop Report | Fasli year (1416 = 2006-07) | **UNVERIFIED** | **NOT PERFORMED** |
| Minor Irrigation Census | Census reference year | n/a | **NOT PERFORMED** |
| ICRISAT DLD | Agricultural year (to be confirmed) | **UNVERIFIED** | **NOT PERFORMED** |

The fasli year in South India is conventionally July–June, but this has **not been confirmed from a primary document** and is therefore not treated as established. HarvestWise's own Kharif window is 1 June – 30 November (`ingestion/district_season_calendar.py`), so a fasli-year irrigation figure is an **annual** quantity that does not align one-to-one with a Kharif window. That mismatch is a methodological decision, not a clerical one.
