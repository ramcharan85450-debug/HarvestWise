# Tamil Nadu overlap-year yield data — source metadata

| Field | Value |
|---|---|
| Publisher | Government of India, Ministry of Agriculture and Farmers Welfare |
| Platform | data.gov.in (Open Government Data Platform India) |
| Resource ID | `35be999b-0208-4354-b557-f6ca9a5355de` |
| Source URL | https://data.gov.in/resource/35be999b-0208-4354-b557-f6ca9a5355de |
| Source file on disk | `data/raw/external/datagovin/district_yield_rice.csv` |
| Fetch code | `ingestion/datagovin_fetch.py` (`filters[crop]=Rice`) |
| Extraction code | `ingestion/tamil_nadu_overlap_extract.py` |
| Crop | Rice |
| State | Tamil Nadu |
| Geographic level | District (31 districts) |
| Years | 2000–2012 |
| Season | Kharif |
| Rows | 381 |
| Area unit | hectares (corroborated — see validation report §3) |
| Production unit | tonnes (corroborated — see validation report §3) |
| Yield | derived as production / area, t/ha, recomputed and cross-checked |

## Why this is a separate directory from `tamil_nadu/`

`official_yield/tamil_nadu/` holds the 2019 and 2024 records collected from the
Tamil Nadu DES Season and Crop Reports (PDF). These overlap-year records come
from a different publication (the national GoI/data.gov.in APY resource) with a
different retrieval date and different source documents. Merging them into one
file would destroy that distinction. They are kept apart so every row's
provenance remains traceable to its own source, and so the two cohorts can be
compared against each other — which Experiment 3's Isolation 2 does.

## Relationship to Andhra Pradesh and Telangana

These rows come from the SAME resource, fetched by the SAME code, with the SAME
unit evidence as `official_yield/andhra_pradesh/` and `official_yield/telangana/`.
That is deliberate: the scientific purpose is a cross-region comparison in
common years, and a different publisher would have removed a temporal confound
while introducing a source confound.

## Validation

See `../OVERLAP_COLLECTION_VALIDATION.md`. Four extreme yield values are present
in the source and are retained and disclosed rather than removed.
