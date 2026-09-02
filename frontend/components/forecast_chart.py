import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_forecast_chart(forecast_df: pd.DataFrame):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=pd.concat([forecast_df["week"], forecast_df["week"][::-1]]),
            y=pd.concat([forecast_df["yield_high"], forecast_df["yield_low"][::-1]]),
            fill="toself",
            fillcolor="rgba(47, 110, 92, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            hoverinfo="skip",
            name="Uncertainty band",
            showlegend=True,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=forecast_df["week"],
            y=forecast_df["yield_median"],
            mode="lines+markers",
            line=dict(color="#2F6E5C", width=3),
            marker=dict(size=5),
            name="Median forecast",
        )
    )

    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        height=380,
        xaxis_title="Week",
        yaxis_title="Yield (t/ha)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
    )

    st.plotly_chart(fig, use_container_width=True)
