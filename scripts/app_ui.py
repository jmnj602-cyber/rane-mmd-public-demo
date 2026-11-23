"""Shared Streamlit page configuration and RANE workspace branding."""

from __future__ import annotations

import streamlit as st

from scripts.data_paths import get_data_mode


DEMO_DISCLAIMER = (
    "PUBLIC DEMO | SYNTHETIC ILLUSTRATIVE DATA | NOT ACTUAL RANE OR LIVE MARKET DATA"
)


def configure_page(page_title: str, page_icon: str) -> None:
    """Apply consistent browser titles, wide layout, and sidebar branding."""
    st.set_page_config(
        page_title=f"RANE MMD | {page_title}",
        page_icon=page_icon,
        layout="wide",
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
    st.sidebar.caption("Management Decision Engine")
    st.sidebar.divider()
