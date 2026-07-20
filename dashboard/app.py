# app.py
# Entry point. Run with: streamlit run app.py (from inside dashboard/)
# Sets page config, loads data once, and shows a barebones landing state.
# The pages/ folder gives the sidebar nav automatically (Streamlit multipage).
# Full Beranda content is built last (Section 6.1, 7). This is a stub only.

import streamlit as st

from core import loader
from core import clean

st.set_page_config(
    page_title="SSDC Dashboard",
    layout="wide",
)

raw = loader.load_data()
data = clean.clean_data(raw)

st.sidebar.caption("Data per " + str(data.ANCHOR.date()))

st.title("SSDC Dashboard")
st.write("Rows: company " + str(len(data.company))
         + ", talent_request " + str(len(data.talent_request))
         + ", student_all " + str(len(data.student_all))
         + ", status_student " + str(len(data.status_student))
         + ", tracking_company " + str(len(data.tracking_company))
         + ", tracking_student " + str(len(data.tracking_student)))
