"""
Analytics Dashboard page.

Implements the spec's "Analytics Dashboard" requirement: intent breakdown,
confidence trends, retrieved documents, conversation history, tool usage,
and processing time — sourced from GET /api/v1/analytics/summary.

Streamlit auto-discovers any .py file under frontend/pages/ and adds it as
a navigable page in the sidebar, with the main frontend/app.py as the
landing page.
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Streamlit runs each page as its own script context, so the sibling
# api_client module (in frontend/, one level up from pages/) needs to be
# added to sys.path explicitly to be importable here.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from api_client import get_analytics_summary  # noqa: E402

st.set_page_config(page_title="Analytics — TechNova Cloud", page_icon="📊", layout="wide")

st.title("📊 Support Agent Analytics")
st.caption("Live metrics from the AI support agent's recent interactions.")

limit = st.slider("Number of recent interactions to analyze", min_value=10, max_value=500, value=50, step=10)

summary = get_analytics_summary(limit=limit)

if summary is None:
    st.stop()

if summary["total_interactions"] == 0:
    st.info("No interactions logged yet. Go chat with the agent first!")
    st.stop()

# ---------------------------------------------------------------------------
# Top-level KPI metrics
# ---------------------------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Interactions", summary["total_interactions"])
col2.metric("Avg. Confidence", f"{summary['average_confidence']:.0%}")
col3.metric("Escalation Rate", f"{summary['escalation_rate']:.0%}")
col4.metric("Avg. Response Time", f"{summary['average_processing_time_ms']:.0f} ms")

st.divider()

# ---------------------------------------------------------------------------
# Breakdown charts
# ---------------------------------------------------------------------------

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Requests by Intent")
    intent_df = pd.DataFrame(
        list(summary["intent_breakdown"].items()), columns=["Intent", "Count"]
    )
    fig = px.pie(intent_df, names="Intent", values="Count", hole=0.4)
    fig.update_layout(showlegend=True, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    st.subheader("Tool Usage")
    tool_df = pd.DataFrame(
        list(summary["tool_usage_breakdown"].items()), columns=["Tool", "Count"]
    )
    fig2 = px.bar(tool_df, x="Tool", y="Count", color="Tool")
    fig2.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Confidence over time (trend)
# ---------------------------------------------------------------------------

st.subheader("Confidence & Processing Time Trend")

logs = summary["recent_logs"]
trend_df = pd.DataFrame(logs)
trend_df["created_at"] = pd.to_datetime(trend_df["created_at"])
trend_df = trend_df.sort_values("created_at")

trend_col1, trend_col2 = st.columns(2)
with trend_col1:
    fig3 = px.line(trend_df, x="created_at", y="response_confidence", markers=True, title="Confidence Over Time")
    fig3.add_hline(y=0.6, line_dash="dash", line_color="orange", annotation_text="Clarify threshold")
    fig3.add_hline(y=0.3, line_dash="dash", line_color="red", annotation_text="Escalate threshold")
    fig3.update_layout(margin=dict(t=40, b=10, l=10, r=10))
    st.plotly_chart(fig3, use_container_width=True)

with trend_col2:
    fig4 = px.line(trend_df, x="created_at", y="processing_time_ms", markers=True, title="Response Time Over Time")
    fig4.update_layout(margin=dict(t=40, b=10, l=10, r=10))
    st.plotly_chart(fig4, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Raw interaction log table
# ---------------------------------------------------------------------------

st.subheader("Recent Interaction Log")

display_df = trend_df[[
    "created_at", "session_id", "user_query", "intent",
    "response_confidence", "tool_used", "escalated", "processing_time_ms",
]].rename(columns={
    "created_at": "Timestamp",
    "session_id": "Session",
    "user_query": "Query",
    "intent": "Intent",
    "response_confidence": "Confidence",
    "tool_used": "Tool",
    "escalated": "Escalated",
    "processing_time_ms": "Time (ms)",
})
display_df = display_df.sort_values("Timestamp", ascending=False)

st.dataframe(
    display_df,
    use_container_width=True,
    column_config={
        "Confidence": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
        "Escalated": st.column_config.CheckboxColumn(),
    },
    hide_index=True,
)
