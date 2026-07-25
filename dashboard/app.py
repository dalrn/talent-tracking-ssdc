# app.py
# Entry point and navigation controller. Run with: streamlit run app.py
#
# Uses st.navigation (not the automatic pages/ folder nav) so that:
#  - there is no stray "app" entry in the sidebar,
#  - the global CSS (S.inject) and the shared sidebar are rendered ONCE here,
#    around every page, which removes the flash of unstyled Streamlit that the
#    per-page inject caused on each navigation.
# The page scripts in pages/ render only their own body; they no longer call
# set_page_config, S.inject, or SB.render_sidebar themselves.

import streamlit as st

from core import loader
from core import clean
from components import styles as S
from components import sidebar as SB

st.set_page_config(
    page_title="SSDC Dashboard",
    layout="wide",
)

# Global CSS once, before any page body renders. Single injection point kills
# the per-page flash of unstyled content.
S.inject()

# Data loaded once (cached) and the shared sidebar rendered once, around the
# selected page. render_sidebar writes st.session_state["rentang_periode"],
# which each page reads and applies to its own data.
raw = loader.load_data()
data = clean.clean_data(raw)
SB.render_sidebar(data)

# Page registry. Beranda is the default (first) page, so opening the app lands
# straight on the action queue. Titles here are the sidebar nav labels.
pages = [
    st.Page("pages/1_Beranda.py", title="Beranda", default=True),
    st.Page("pages/2_Matching.py", title="Matching"),
    st.Page("pages/3_Monitoring.py", title="Monitoring"),
    st.Page("pages/4_Analitik.py", title="Analitik"),
]

st.navigation(pages).run()
