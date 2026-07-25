# components/sidebar.py
# Owner: shared. Sidebar footer + global date filter, called by every page so
# the sidebar reads the same on all of them (Streamlit multipage does not carry
# a sidebar built in app.py into pages/).
#
# The date filter writes st.session_state["rentang_periode"] as a
# (start, end) pair of pandas Timestamps, or None when the range covers the
# full dataset (so pages treat "no filter" and "full range" the same).
# Basis: send_date (per spec Section 5.4). Matching applies it to request_date
# for its request list; the value here is date-only and page-agnostic.

from pathlib import Path

import pandas as pd
import streamlit as st

import config
from components import html as H

WARNA = config.WARNA

# CDC logo shown at the top of the sidebar. Drop a file here (PNG with a
# transparent background works best) and it appears automatically. Any of these
# names is picked up, first match wins. Resolved relative to the dashboard/
# folder so it works no matter the current working directory.
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_LOGO_CANDIDATES = [
    "cdc_logo.png", "cdc_logo.svg", "cdc_logo.jpg", "cdc_logo.jpeg",
    "logo_cdc.png", "logo.png",
]


def _find_logo():
    """Return the first existing logo file path, or None if none is present."""
    for name in _LOGO_CANDIDATES:
        candidate = _ASSETS_DIR / name
        if candidate.exists():
            return str(candidate)
    return None


def _period_bounds(tracking_company):
    """Earliest and latest send_date in the data, as python dates."""
    sd = pd.to_datetime(tracking_company["send_date"], errors="coerce").dropna()
    return sd.min().date(), sd.max().date()


def render_sidebar(data):
    """Render the shared sidebar: page nav on top, filter + footer pinned bottom.

    Reads/writes st.session_state["rentang_periode"]. Returns the resolved
    (start, end) Timestamp pair or None (full range). Pages call this once near
    the top and apply the returned range to their send_date based data.

    The filter and the "Data per ..." footer are pushed to the bottom of the
    sidebar. Streamlit renders sidebar children top to bottom, so a flex rule
    (margin-top:auto on the marked block) floats this block below the nav.
    """
    lo, hi = _period_bounds(data.tracking_company)

    # Pin the filter block to the bottom of the sidebar. Make the sidebar
    # content a full-height flex column, then let the block that contains the
    # .sb-bottom marker take margin-top:auto so it floats to the bottom, below
    # the page nav. Colors from config.WARNA, no hex literal.
    st.markdown(
        "<style>"
        # The sidebar content wrapper becomes a full-height flex column.
        "section[data-testid='stSidebar'] > div:first-child"
        "{display:flex;flex-direction:column;min-height:100vh;}"
        "section[data-testid='stSidebar'] [data-testid='stSidebarUserContent']"
        "{display:flex;flex-direction:column;flex:1;}"
        # The vertical block that holds the marker floats to the bottom.
        "section[data-testid='stSidebar'] div[data-testid='stVerticalBlock']"
        ":has(.sb-bottom){margin-top:auto;border-top:1px solid "
        + WARNA["line"] + ";padding-top:12px;}"
        "</style>",
        unsafe_allow_html=True,
    )

    # Work title, shown above the logo at the very top of the sidebar.
    with st.sidebar:
        st.markdown(
            "<div style='color:#000000;font-size:1rem;font-weight:700;"
            "line-height:1.4;margin-bottom:8px;'>INTEGRASI DASHBOARD "
            "INTERAKTIF UNTUK OPTIMALISASI KINERJA CAREER DEVELOPMENT "
            "CENTER (CDC)</div>",
            unsafe_allow_html=True,
        )

    # CDC logo at the top of the sidebar. Shown only if a logo file is present
    # in dashboard/assets (see _LOGO_CANDIDATES); the sidebar renders cleanly
    # without it otherwise, so a missing file is never an error.
    logo_path = _find_logo()
    if logo_path:
        with st.sidebar:
            st.image(logo_path, use_container_width=True)

    with st.sidebar:
        with st.container():
            st.markdown("<span class='sb-bottom'></span>", unsafe_allow_html=True)
            st.markdown("**Filter tanggal**")
            st.caption("Basis: tanggal pengiriman (send_date).")
            picked = st.date_input(
                "Rentang tanggal",
                value=(lo, hi),
                min_value=lo,
                max_value=hi,
                key="rentang_periode_input",
                format="DD/MM/YYYY",
            )
            st.caption("Data per " + H.tanggal_id(data.ANCHOR.date()))
            st.markdown(
                "<div style='color:" + WARNA["navy"] + ";font-size:0.8rem;"
                "font-weight:700;line-height:1.4;margin-top:24px;'>"
                "matplotlibur<br>SSDC2026045</div>",
                unsafe_allow_html=True,
            )

    # date_input returns a single date until both ends are picked. Guard that.
    if isinstance(picked, (tuple, list)) and len(picked) == 2:
        start, end = picked
    else:
        start, end = lo, hi

    # Store None when the pick spans the whole dataset, so downstream pages do
    # not needlessly filter (and the "no filter" and "full range" cases match).
    if start <= lo and end >= hi:
        st.session_state["rentang_periode"] = None
        resolved = None
    else:
        resolved = (pd.Timestamp(start), pd.Timestamp(end))
        st.session_state["rentang_periode"] = resolved

    return resolved
