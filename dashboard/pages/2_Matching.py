# pages/2_Matching.py
# Owner: Mutia. Purpose: Matching (BT-01, BT-03, BT-06). See spec Section 6.2.

import pandas as pd
import streamlit as st
from streamlit_searchbox import st_searchbox

import config
from core import clean, loader, metrics, schema, matching_engine
from components import html as H
from components import styles as S


WARNA = config.WARNA


# Data. Loaded and cleaned once by the cached loader.

st.set_page_config(page_title="Matching", layout="wide")
S.inject()

raw = loader.load_data()
data = clean.clean_data(raw)

ts = data.tracking_student
tc = data.tracking_company
ss = data.status_student
sa = data.student_all
co = data.company
tr = data.talent_request
ANCHOR = data.ANCHOR
st.markdown(
    H.page_header(
        "Talent Matching",
        "Cocokkan permintaan perusahaan yang belum digarap dengan mahasiswa "
        "yang paling sesuai.",
        eyebrow="Pencocokan Talenta",
    ),
    unsafe_allow_html=True,
)


# cell matching
c1, c2 = st.columns([1.5, 3.2]) # bagi kolom

draft_req = metrics.draft_requests(tc) # ambil draft request dari trackimg company
draft_req["label"] = (draft_req["nama_perusahaan"]+"-"+draft_req["posisi"]) # label searching
draft_req["days_left"] = (ANCHOR - draft_req["request_date"]).dt.days
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

c1_cols = [ 'nama_perusahaan', 'posisi',
           'jumlah_permintaan', 'jumlah_dikirimkan', "days_left"
           ]
# design kolom 1
with c1:
    with st.container(height = 1500):
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
                              ["Terbaru", "Terlama", "Mahasiswa Dibutuhkan (min)", "Mahasiswa Dibutuhkan (max)"],
                              key = "req_sort")
        if option == "Terbaru":
            req_sorted = draft_req.sort_values("request_date", ascending = False)
        elif option == "Terlama":
            req_sorted = draft_req.sort_values("request_date", ascending = True)
        elif option == "Mahasiswa Dibutuhkan (min)":
            req_sorted = draft_req.sort_values("jumlah_permintaan", ascending = True) 
        else:
            req_sorted = draft_req.sort_values("jumlah_permintaan", ascending = False)

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

            # st.write(selected_req['id_talent_req'])


# design kolom 2
with c2:
    with st.container(height = 400):
        if not event.selection.rows:
            st.info("Pilih untuk Melihat Detail Informasi Request dan Mahasiswa yang Sesuai Kebutuhan Perusahaan")
        else:
            idx = event.selection.rows[0]
            req = req_show.iloc[idx]
            tr_req = tr.loc[tr['id_talent_req']==req['id_talent_req']].iloc[0]
            co_req = co.loc[co['id_company']== req['id_company']].iloc[0]

            # st.dataframe(req)
            # st.dataframe(tr_req)
            # st.dataframe(co_req)
            
            
            st.subheader(req["id_talent_req"])
            st.title(req['posisi'])
            st.markdown(req['nama_perusahaan'] + "")
            st.markdown("Kompensasi: " + tr_req['renumerasi'])
            st.markdown("Durasi penempatan: " + tr_req["durasi"])

            # magang, 3 orang (x terpilih), hybrid, yogyakarta, min sems. bawahnya tools, prodi, min ipk
            c1, c2, c3, c4, c5, c6 = st.columns([1,1,1,1,1,1])

            with c1:
                st.markdown(tr_req['jenis_penempatan'])
            with c2:
                st.markdown(str(tr_req["headcount"]) + " Orang")
            with c3:
                st.markdown(tr_req["working_arrangement_detail"])
            with c4:
                st.markdown(co_req["kota"])
            with c5:
                st.markdown("min. semester " + str(tr_req['minimum_semester']))
            with c6:
                st.markdown("Program studi sesuai: ")  
                st.pills(
                    label = "",
                    options = req['bidang_studi_dicari_list'],
                    selection_mode = "multi",
                )  

            st.markdown("Kriteria diperlukan: " + tr_req['deskripsi_requirement']) 


    """
    INI BAGIAN MATCHING SEBENTAR BINGUNG INIANNYA
    """
    with st.container(height = 300):
        st.markdown("ringkasan hasil matching")
        ...
    with st.container(height = 800):
        st.markdown("talent option")
        ...


        

