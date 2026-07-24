# app.py
# Entry point. Run with: streamlit run app.py (from inside dashboard/)
# Sets page config, loads data once, and shows a barebones landing state.
# The pages/ folder gives the sidebar nav automatically (Streamlit multipage).
# Full Beranda content is built last (Section 6.1, 7). This is a stub only.

import streamlit as st

from core import loader
from core import clean
from components import html as H
from components import styles as S

st.set_page_config(
    page_title="SSDC Dashboard",
    layout="wide",
)
S.inject()

raw = loader.load_data()
data = clean.clean_data(raw)

st.sidebar.caption("Data per " + str(data.ANCHOR.date()))

st.markdown(
    H.page_header(
        "SSDC Dashboard",
        "Talent tracking untuk CDC. Pilih halaman di panel kiri: Beranda untuk "
        "antrean aksi, Matching untuk pencocokan, Monitoring untuk funnel dan "
        "ghosting, Analitik untuk laporan kinerja.",
        eyebrow="Career Development Center",
        stamp="Data per " + str(data.ANCHOR.date()),
    ),
    unsafe_allow_html=True,
)
