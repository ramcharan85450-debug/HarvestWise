# Harvest outcome records — what goes here and why it matters

This directory is **empty on purpose**. It is the project's highest-priority
outstanding data item, and the one thing in the pipeline that cannot be
derived, downloaded, or modelled from anything else.

## What it is

A record of what a grower *actually did and got*, per season:

| column | meaning |
|---|---|
| `season_start_date` | sowing / transplanting date (ISO, `YYYY-MM-DD`) |
| `recommended_window_start` | start of the window the system recommended |
| `recommended_window_end` | end of that window |
| `actual_harvest_date` | when it was actually harvested |
| `actual_yield_t_ha` | realised yield, tonnes per hectare |
| `fixed_date_baseline_date` | the grower's usual/customary harvest date |
| `fixed_date_baseline_yield_t_ha` | yield from that customary date, if known |

Save one file per field as `{field_id}_outcomes.csv` (e.g. `F001_outcomes.csv`),
using `TEMPLATE_outcomes.csv` as the header. Every `FILL_` placeholder must be
replaced — `evaluation/outcome_validation/backtest_real_outcomes.py` reads
these directly and any placeholder left in place will fail loudly rather than
be silently coerced.

## Why it cannot be substituted

The project's three claims are: a climate-shock benchmark, an RL harvest-window
policy, and **validation against real harvest outcomes**. The third has no
evidence at all without this file. A yield-forecast accuracy number does not
substitute for it: forecasting a season's yield and demonstrating that acting
on a recommended harvest window produced a better result are different claims,
and only the second justifies the "dynamic harvest window optimization" in the
project's title.

This directory previously had its absence papered over: `backend/app/services/
outcome_service.py` returned nine invented seasons ("Rabi 2023, +0.62 t/ha over
the fixed-date baseline") which the dashboard rendered under the heading "the
evidence behind the real-outcome-validation claim". Those were removed. An
empty directory is an honest limitation; invented records are misconduct.

## Realistic sources

Even **one field over two or three seasons** is enough to demonstrate the
method end to end — it would not support a general claim, and the write-up must
say so, but it converts "no evidence" into "a documented case study", which is
a very different thing in review.

- A farmer you or your family know, with their own harvest records
- Your college / university agriculture department's research plots
- The local **Krishi Vigyan Kendra (KVK)** — district-level agricultural
  extension centres keep exactly this kind of record
- A farmer producer organisation or cooperative society
- State agriculture department demonstration plots

Ask specifically for: sowing date, harvest date, and yield per hectare, for as
many recent seasons as they have. The recommended-window columns can be filled
in afterwards by running the trained policy over that field's season.

## Recording provenance

Add a short note here naming the source (institution or "grower, district X"),
the date obtained, and whether the figures are recorded measurements or recall.
Recall-based yields are still usable, but the distinction belongs in the paper.
