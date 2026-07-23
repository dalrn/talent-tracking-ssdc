# pages/2_Matching.py
# Owner: Mutia. Purpose: Matching (BT-01, BT-03, BT-06). See spec Section 6.2.

import pandas as pd
import streamlit as st
from streamlit_searchbox import st_searchbox
import config

from core import clean, loader, metrics, schema, matching_engine
from components import html as H


WARNA = config.WARNA


# Data. Loaded and cleaned once by the cached loader.

raw = loader.load_data()
data = clean.clean_data(raw)

ts = data.tracking_student
tc = data.tracking_company
ss = data.status_student
sa = data.student_all
co = data.company
tr = data.talent_request
ANCHOR = data.ANCHOR

st.set_page_config(page_title="Matching", layout="wide")
st.title("Talent Matching")


# cell matching
c1, c2 = st.columns([1.5, 3.2]) # bagi kolom

draft_req = metrics.draft_requests(tc) # ambil draft request dari trackimg company
draft_req["label"] = (draft_req["nama_perusahaan"]+"-"+draft_req["posisi"]) # label searching
req_days = metrics.request_age_days(tc, ANCHOR)
orphan = metrics.orphan_talent_req(tr, tc) # jujur belum tau buat apa
n_req = draft_req['id_talent_req'].nunique()


# searching request
def search_request(searchterm):
    if not searchterm:
        return draft_req["label"].tolist()
    mask = draft_req["label"].str.contains(
        searchterm,
        case = False,
        na = False
    )
    return draft_req.loc[mask,"label"].tolist()

c1_cols = [ 'nama_perusahaan', 'posisi', 'jenis_penempatan', 'bidang_studi_dicari_list', 
           'jumlah_permintaan', 'jumlah_dikirimkan'
           ]
# design kolom 1
with c1:
    with st.container(height = 500):
        cel1, cel2 = st.columns([1,1])
        with cel1:
            st.markdown("**Permintaan Terbuka**")
        with cel2:
            st.markdown(
                f"<div style='text-align: right;'><b>{str(n_req)}</b> belum dikirimkan</div>",
                unsafe_allow_html=True
            )

        # search box
        selected = st_searchbox(
            search_function = search_request,
            placeholder = "Cari Perusahaan atau Posisi",
            key = "req_search"
        )

        # filterbox
        option = st.selectbox("Urutkan",
                              ["Terbaru", "Terlama", "Mahasiswa Dibutuhkan"],
                              key = "req_sort")
        if option == "Terbaru":
            req_sorted = draft_req.sort_values("request_date", ascending = False)
        elif option == "Terlama":
             req_sorted = draft_req.sort_values("request_date", ascending = True)
        else:
            req_sorted = draft_req.sort_values("jumlah_permintaan", ascending = True)

        # masuk css html nanti yang kepilih dikaish warna highlight
        if selected:
            selected_rows = req_sorted[req_sorted['label']==selected]
            other_rows = req_sorted[req_sorted['label']!= selected]

            req_show = pd.concat([selected_rows, other_rows], ignore_index = True)
        else:
            req_show = req_sorted 

        
        # show 
        event = st.dataframe(
            req_show[c1_cols],
            use_container_width= True,
            hide_index=True,
            on_select = "rerun",
            selection_mode = 'single-row'
        ) 
        if event.selection.rows:
            idx = event.selection.rows[0]
            selected_req = req_show.iloc[idx]

            st.write(selected_req['id_talent_req'])


# design kolom 2
with c2:
    with st.container(height = 200):
        st.markdown("detail request perusahaan")
        ...
    with st.container(height = 150):
        st.markdown("ringkasan hasil matching")
        ...
    with st.container(height = 400):
        st.markdown("talent")
        ...


        

