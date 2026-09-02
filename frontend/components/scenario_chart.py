import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_scenario_chart(baseline_df: pd.DataFrame, scenario_df: pd.DataFrame):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=baseline_df["week"],
            y=baseline_df["yield_median"],
            mode="lines",
            line=dict(color="#8B9686", width=2, dash="dot"),
            name="Baseline forecast",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=scenario_df["week"],
            y=scenario_df["yield_median"],
            mode="lines+markers",
            line=dict(color="#A9782B", width=3),
            marker=dict(size=5),
            name="Scenario forecast",
        )
    )

    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        height=340,
        xaxis_title="Week",
        yaxis_title="Yield (t/ha)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
    )

    st.plotly_chart(fig, use_container_width=True)
