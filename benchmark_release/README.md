# HarvestWise Climate-Shock Benchmark

A reusable benchmark for evaluating whether a crop-yield forecasting model
generalizes to anomalous climate years (drought / heatwave / shifted monsoon)
rather than only performing well on the climate-normal years it likely
resembles most in training data.

## What it tests

Standard yield-prediction benchmarks use a random train/test split, which
lets a model do well by memorizing typical seasonal patterns. This benchmark
instead trains only on field-seasons labeled `normal` and evaluates on those
labeled `drought`, `wet_extreme`, or `heatwave` (see
`splits/field_year_labels.json`) - a harder, more realistic test of
climate-adaptive generalization.

Splits are keyed by **(field, year)**, not by year alone, because a drought is
a local event: the same calendar year can be a shock season in Punjab and an
ordinary one in Tamil Nadu. Labels are derived from real ERA5 growing-season
anomalies against each field's own climatology, never assigned by hand.

## Contents

- `splits/field_year_labels.json` - which (field, year) seasons count as normal vs. which climate-shock type, derived from ERA5
- `eval_harness.py` - scores any model's predictions against the splits and produces the metrics below
- `leaderboard.md` - current results (updated as new models are evaluated)

## Metrics

For each model: MAE (t/ha) on normal seasons, MAE on climate-shock seasons,
and the **climate-robustness margin** (shock MAE minus normal MAE - smaller is
better; it measures how much accuracy a model loses under climate stress).
The sample size behind each bucket is returned alongside every score.

MAE is primary rather than R². R² over a handful of held-out seasons is
dominated by the variance of those few points, so the harness returns it as
`None` below 5 examples in a bucket instead of a number that would get quoted
without its n.

## Using this benchmark

```python
from eval_harness import load_splits, score_model

splits = load_splits("splits/field_year_labels.json")
results = score_model(
    your_model_predict_fn,
    your_examples,
    field_year_of_fn=lambda ex: (ex.field_id, int(ex.season_start_date[:4])),
    splits=splits,
)
```

`your_model_predict_fn` should take a list of season examples and return
predicted final yields, in the same order. `field_year_of_fn` extracts the
`(field_id, year)` key. Seasons with no label in the splits file are skipped,
not guessed at.

## Citing

See `CITATION.cff`.

## License

Code: MIT. Split definitions: CC-BY-4.0.

## Status

Version 1.0, covering rice and wheat across 7 real fields in Tamil Nadu,
Punjab, West Bengal and Andhra Pradesh, built as a final-year project's
evaluation methodology.

**Current scale is small and stated plainly:** 24 labelled field-seasons, of
which 4 cross the shock thresholds. See `leaderboard.md` for what that does
and does not support - including that the project's own multimodal model
currently loses to a Random Forest baseline on this benchmark. Contributions
of splits/labels for other crops and regions are welcome via pull request.
