import streamlit as st

from components.api_client import fetch_outcomes
from components.field_selector import render_field_selector

st.set_page_config(page_title="Past Outcomes - HarvestWise", page_icon="🌾", layout="wide")

st.title("Past Seasons — Recommended vs. Actual")
field_id = render_field_selector()

st.write(
    "Backtests the recommended harvest window against what actually happened and against "
    "a naive fixed-date harvest — the evidence behind the real-outcome-validation claim."
)

outcomes = fetch_outcomes(field_id)

if outcomes.empty:
    st.warning(
        "**No real harvest-outcome records exist for this field.**\n\n"
        "`data/raw/harvest_outcomes/` is empty. Real-outcome validation is the project's "
        "highest-priority outstanding data item and needs records from a grower, "
        "cooperative or agri-board case study — see "
        "`evaluation/outcome_validation/backtest_real_outcomes.py` for the required columns.\n\n"
        "This page deliberately shows nothing rather than the placeholder seasons it used to "
        "display, which were invented and rendered under a heading claiming they were evidence.",
        icon="📋",
    )
else:
    cols = st.columns(len(outcomes))
    for col, (_, row) in zip(cols, outcomes.iterrows()):
        gain = row["actual_yield_t_ha"] - row["fixed_date_baseline_yield_t_ha"]
        with col:
            st.markdown(f"**{row['season']}**")
            st.markdown(f"##### {row['recommended_window']}")
            st.caption(f"Actual harvest date: {row['actual_harvest_date']}")
            st.metric("Realized yield", f"{row['actual_yield_t_ha']:.2f} t/ha")
            st.metric("vs. fixed-date baseline", f"+{gain:.2f} t/ha")

    st.divider()
    avg_gain = (outcomes["actual_yield_t_ha"] - outcomes["fixed_date_baseline_yield_t_ha"]).mean()
    st.success(
        f"Across {len(outcomes)} logged seasons, the recommended window averaged "
        f"**+{avg_gain:.2f} t/ha** over a fixed-date harvest baseline.",
        icon="✅",
    )

with st.expander("Raw outcome data"):
    st.dataframe(outcomes, use_container_width=True)
