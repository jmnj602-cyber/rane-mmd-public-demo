"""Shared Streamlit page configuration and RANE workspace branding."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from scripts.data_paths import get_data_mode


DEMO_DISCLAIMER = (
    "PUBLIC DEMO | SYNTHETIC ILLUSTRATIVE DATA | NOT ACTUAL RANE OR LIVE MARKET DATA"
)
CHART_PALETTE = [
    "#2C6782",
    "#4B8297",
    "#6F9EA4",
    "#8292A4",
    "#3D7C78",
]


def _configure_plotly_theme() -> None:
    template = go.layout.Template(pio.templates["plotly_white"])
    template.layout.update(
        colorway=CHART_PALETTE,
        font={
            "family": "Arial, sans-serif",
            "size": 12,
            "color": "#26384A",
        },
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        xaxis={
            "gridcolor": "#E7EDF2",
            "linecolor": "#CCD6DF",
            "zerolinecolor": "#D3DDE5",
        },
        yaxis={
            "gridcolor": "#E7EDF2",
            "linecolor": "#CCD6DF",
            "zerolinecolor": "#D3DDE5",
        },
    )
    pio.templates["rane_corporate"] = template
    px.defaults.template = "rane_corporate"
    px.defaults.color_discrete_sequence = CHART_PALETTE
    px.defaults.color_continuous_scale = "Blues"


def configure_page(page_title: str) -> None:
    """Apply consistent browser titles, wide layout, and sidebar branding."""
    st.set_page_config(
        page_title=f"RANE MMD | {page_title}",
        page_icon=None,
        layout="wide",
    )
    _configure_plotly_theme()
    st.markdown(
        """
        <style>
        :root {
            --rane-ink: #1d3044;
            --rane-navy: #142b43;
            --rane-blue: #2c6782;
            --rane-teal: #3d7c78;
            --rane-slate: #607387;
            --rane-border: #dce4eb;
            --rane-surface: #ffffff;
            --rane-background: #f4f7fa;
        }
        .stApp,
        [data-testid="stAppViewContainer"] {
            background: var(--rane-background);
            color: var(--rane-ink);
        }
        [data-testid="stHeader"] {
            background: rgba(244, 247, 250, 0.96);
        }
        [data-testid="stAppViewContainer"] .main .block-container {
            max-width: 1500px;
            padding: 1.65rem 2.15rem 3rem;
        }
        [data-testid="stSidebar"] {
            background: #eef2f6;
            border-right: 1px solid var(--rane-border);
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
            color: var(--rane-navy);
            font-size: 1.05rem;
            font-weight: 650;
            letter-spacing: 0.01em;
        }
        [data-testid="stMarkdownContainer"] h1 {
            color: var(--rane-navy);
            font-size: 2rem;
            font-weight: 650;
            line-height: 1.2;
            letter-spacing: -0.025em;
            margin-bottom: 0.35rem;
        }
        [data-testid="stMarkdownContainer"] h2 {
            color: var(--rane-navy);
            font-size: 1.4rem;
            font-weight: 620;
            letter-spacing: -0.01em;
            padding-top: 0.45rem;
        }
        [data-testid="stMarkdownContainer"] h3 {
            color: var(--rane-ink);
            font-size: 1.08rem;
            font-weight: 620;
        }
        .rane-eyebrow {
            color: var(--rane-slate);
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.13em;
            margin: 0 0 0.4rem;
            text-transform: uppercase;
        }
        [data-testid="stMetric"] {
            background: var(--rane-surface);
            border: 1px solid var(--rane-border);
            border-left: 3px solid var(--rane-blue);
            border-radius: 4px;
            box-shadow: none;
            padding: 0.75rem 0.95rem;
        }
        [data-testid="stMetricLabel"] p {
            color: var(--rane-slate);
            font-size: 0.78rem;
            font-weight: 600;
        }
        [data-testid="stMetricValue"] {
            color: var(--rane-navy);
            font-size: 1.55rem;
            font-weight: 650;
        }
        [data-testid="stAlert"] {
            border-radius: 4px;
            box-shadow: none;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid var(--rane-border);
            border-radius: 4px;
        }
        [data-testid="stTabs"] button {
            color: var(--rane-slate);
            font-weight: 600;
        }
        div.stButton > button,
        div.stDownloadButton > button,
        div[data-testid="stLinkButton"] > a {
            border-radius: 4px;
            font-weight: 600;
        }
        hr {
            border-color: var(--rane-border);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="rane-eyebrow">RANE MMD&nbsp;&nbsp; | &nbsp;&nbsp;MANAGEMENT DECISION ENGINE</div>',
        unsafe_allow_html=True,
    )
    try:
        mode = get_data_mode()
    except ValueError as error:
        st.error(f"Invalid data mode configuration: {error}")
        st.stop()
    if mode == "demo":
        st.warning(DEMO_DISCLAIMER)
    else:
        st.info("PRIVATE DEVELOPMENT MODE | Local workspace data may be unapproved.")
    st.sidebar.markdown("### RANE MMD")
    st.sidebar.caption("Management decision support")
    st.sidebar.divider()
