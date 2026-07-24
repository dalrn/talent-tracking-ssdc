# pages/2_Matching.py
# Owner: Mutia. Purpose: Matching (BT-01, BT-03, BT-06). See spec Section 6.2.

import pandas as pd
import streamlit as st
from streamlit_searchbox import st_searchbox

import config
from core import clean, loader, metrics, schema, matching
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


@st.cache_resource(show_spinner="Memproses pencarian...")
def _get_matching_engine():
    """Build and precompute MatchingEngine once per session.

    Cached as a resource (not cache_data): precompute() builds the tool
    lexicon and historical knowledge dictionary from the full student and
    tracking tables, expensive to redo on every widget interaction. Fed the
    same already-cleaned dataframes every other section of this page uses,
    not a second raw CSV read.
    """
    raw_ = loader.load_data()
    cleaned = clean.clean_data(raw_)
    engine = matching.MatchingEngine(dataframes={
        "student_all": cleaned.student_all,
        "status_student": cleaned.status_student,
        "tracking_student": cleaned.tracking_student,
        "tracking_company": cleaned.tracking_company,
        "talent_request": cleaned.talent_request,
        "company": cleaned.company,
    })
    engine.initialize()
    return engine



st.markdown(
    H.page_header(
        "Talent Matching",
        "Cocokkan permintaan perusahaan yang belum digarap dengan mahasiswa "
        "yang paling sesuai.",
        eyebrow="Pencocokan Talenta",
    ),
    unsafe_allow_html=True,
)


st.session_state.setdefault("request_table_version", 0)
st.session_state.setdefault("selected_candidate_ids", [])
st.session_state.setdefault("active_request_id", None)
st.session_state.setdefault("sent_candidates", {})

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
        f1, f2 = st.columns([1,1])
        with f2:
            option = st.selectbox(
                "Urutkan",
                ["Terbaru", "Terlama", "(asc) Mahasiswa Dibutuhkan", "(desc) Mahasiswa Dibutuhkan"],
                key = "req_sort"
            )
        with f1:
            headcount_options = sorted(draft_req['jumlah_permintaan'].unique())
            selected_hc = st.multiselect(
                "Mahasiswa Dibutuhkan",
                options = headcount_options,
                default=headcount_options,
                key = "req_headcount_filter"
            )
        # filter
        if selected_hc:
            req_filtered = draft_req[draft_req["jumlah_permintaan"].isin(selected_hc)]
        # sort
        if option == "Terbaru":
            req_sorted = req_filtered.sort_values("request_date", ascending = False)
        elif option == "Terlama":
            req_sorted = req_filtered.sort_values("request_date", ascending = True)
        elif option == "Mahasiswa Dibutuhkan (min)":
            req_sorted = req_filtered.sort_values("jumlah_permintaan", ascending = False) 
        else:
            req_sorted = req_filtered.sort_values("jumlah_permintaan", ascending = True)

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

        if st.button(
            "Reset request terpilih",
            use_container_width=True,
            key="reset_selected_request",
        ):
            metrics.reset_selected_request()
            st.rerun()



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
            st.markdown(tr_req['renumerasi'])
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
                st.markdown("min. semester" + str(tr_req['minimum_semester']))
            with c6:
                st.markdown("Program studi sesuai: ")  
                st.pills(
                    label = "",
                    options = req['bidang_studi_dicari_list'],
                    selection_mode = "multi",
                )  

            st.markdown("Kriteria diperlukan: " + tr_req['deskripsi_requirement']) 

    # container bobot dan ringkasan hasil matching
    with st.container(height = 200):
            c1, c2 = st.columns([3,1])
            with c1: 
                st.markdown("### Ringkasan hasil matching")
            if not event.selection.rows:
                with c2:
                    st.empty()
                st.caption("Pilih permintaan di kolom kiri untuk melihat ringkasan matching.")
            else:
                idx = event.selection.rows[0]
                req = req_show.iloc[idx]
                tid = str(req["id_talent_req"])

                with c2:
                    if st.button(
                        "Reset ke bobot default",
                        use_container_width = True,
                        key = f"reset_weight{tid}",
                    ):
                        metrics.reset_matching_weights()
                        st.rerun()
                    
                if st.session_state["active_request_id"] != tid:
                    st.session_state["active_request_id"] = tid
                    st.session_state["selected_candidate_ids"] = []

                engine = _get_matching_engine()

                bw1, bw2, bw3, bw4, bw5, bw6 = st.columns([1,1,1,1,1,1])
                with bw1:
                    bobot_tools = st.slider(
                        "Tools", 0, 100, metrics.default_weight_percent("tool_match"),
                        key="bobot_tool_match",
                    )
                with bw2:
                    bobot_prodi = st.slider(
                        "Program Studi", 0, 100, metrics.default_weight_percent("program_study"),
                        key="bobot_program_study",
                    )
                with bw3:
                    bobot_ipk = st.slider(
                        "IPK", 0, 100, metrics.default_weight_percent("ipk"),
                        key="bobot_ipk",
                    )
                with bw4:
                    bobot_interest = st.slider(
                        "Minat", 0, 100, metrics.default_weight_percent("interest"),
                        key="bobot_interest",
                    )
                with bw5:
                    bobot_lokasi = st.slider(
                        "Lokasi", 0, 100, metrics.default_weight_percent("location"),
                        key="bobot_location",
                    )
                with bw6:
                    bobot_preferensi = st.slider(
                        "Preferensi Penempatan", 0, 100,
                        metrics.default_weight_percent("placement_preference"),
                        key="bobot_placement_preference",
                    )



                
            current_weights = {
                "tool_match": bobot_tools / 100,
                "program_study": bobot_prodi / 100,
                "ipk": bobot_ipk / 100,
                "interest": bobot_interest / 100,
                "location": bobot_lokasi / 100,
                "placement_preference": bobot_preferensi / 100,
            }

            rec_result = engine.recommend(tid, top_n=None, weights=current_weights)

            if rec_result.empty:
                st.markdown(
                    H.callout(
                        "Tidak ada kandidat eligible (Available, status aktif, CV "
                        "ada, semester cukup) untuk permintaan ini.",
                        kind="watch",
                    ),
                    unsafe_allow_html=True,
                )
            # else:
            #     n_eligible = len(rec_result)
            #     n_domisili = int(rec_result["Domisili Sama Kantor"].sum())
            #     n_porto = int(rec_result["Punya Portofolio"].sum())

            #     k1, k2, k3 = st.columns(3)
            #     metrics.render_donut_kpi(
            #         k1, f"kpi_eligible_{tid}", "Mahasiswa eligible",
            #         n_eligible, engine.total_students, WARNA["accent"],
            #         "mahasiswa eligible",
            #     )
            #     metrics.render_donut_kpi(
            #         k2, f"kpi_domisili_{tid}", "Domisili sama dengan kantor",
            #         n_domisili, n_eligible, WARNA["ok"],
            #         "mahasiswa domisili sama dengan kantor",
            #     )
            #     metrics.render_donut_kpi(
            #         k3, f"kpi_porto_{tid}", "Punya portofolio",
            #         n_porto, n_eligible, WARNA["hot"],
            #         "mahasiswa punya portofolio",
            #     )

    # container tabel detail mahasiswa hasil matching
    with st.container(height = 800):
        st.markdown("### Talent yang sesuai")
        if not event.selection.rows or rec_result is None or rec_result.empty:
            st.caption("Belum ada hasil matching untuk ditampilkan.")
        else:
            tid = str(req["id_talent_req"])
            # rec_result sudah lengkap: engine.recommend() (core/matching.py)
            # sudah menggabungkan skor, atribut mahasiswa (Nama, Program Studi,
            # CV, dll.), Jenis Tools Match, dan Request Lain dalam satu tabel.
            detail_df = rec_result

            f1, f2= st.columns([1, 1.4])
            with f1:
                portfolio_filter = st.radio(
                    "Filter portofolio",
                    ["Semua", "Hanya yang ada portofolio"],
                    horizontal=True,
                    key=f"portfolio_filter_{tid}",
                )
            with f2:
                requested_programs = matching.requested_program_options(req)
                program_filter_options = ["Semua prodi"] + requested_programs
                selected_program_filter = st.selectbox(
                    "Filter program studi",
                    program_filter_options,
                    key=f"program_filter_{tid}",
                )

            filtered_detail = detail_df.copy()
            if portfolio_filter == "Hanya yang ada portofolio":
                filtered_detail = filtered_detail[filtered_detail["Punya Portofolio"]]
            if selected_program_filter != "Semua prodi":
                filtered_detail = filtered_detail[
                    filtered_detail["Program Studi"].astype(str).str.lower()
                    == str(selected_program_filter).lower()
                ]

            candidates_with_other = filtered_detail[filtered_detail["Jumlah Request Lain"] > 0]
            if not candidates_with_other.empty:
                with st.expander(
                    f"Lihat detail request lain ({len(candidates_with_other)} kandidat)"
                ):
                    other_id_col = matching.candidate_id_column(candidates_with_other)
                    name_lookup = dict(zip(
                        candidates_with_other[other_id_col].astype(str),
                        candidates_with_other["Nama Mahasiswa"],
                    ))
                    nim_options = list(name_lookup.keys())
                    picked_nim = st.selectbox(
                        "Pilih kandidat",
                        nim_options,
                        format_func=lambda nim: f"{nim} - {name_lookup.get(nim, '')}",
                        key=f"other_request_pick_{tid}",
                    )
                    other_reqs = engine.other_requests(picked_nim, exclude_tid=tid)
                    if not other_reqs:
                        st.caption("Tidak ada request lain untuk kandidat ini.")
                    else:
                        st.markdown(
                            H.read_only_table(
                                ["id_talent_req", "Posisi", "Perusahaan", "Tanggal"],
                                [
                                    [
                                        r["id_talent_req"], r["posisi"], r["perusahaan"],
                                        "" if pd.isna(r["tanggal"]) else str(pd.Timestamp(r["tanggal"]).date()),
                                    ]
                                    for r in other_reqs
                                ],
                                align=["left", "left", "left", "left"],
                            ),
                            unsafe_allow_html=True,
                        )

            top_n_label = st.selectbox(
                "Tampilkan", ["Top 10", "Top 25", "Top 50", "Top 100","Semua"],
                key="matching_top_n",
            )
            n_map = {"Top 10": 10, "Top 25": 25, "Top 50": 50, "Top 100": 100,"Semua": None}
            n_show = n_map[top_n_label]
            show_df = filtered_detail if n_show is None else filtered_detail.head(n_show)

            if show_df.empty:
                st.caption("Tidak ada kandidat yang sesuai dengan filter tabel.")

            id_col = matching.candidate_id_column(show_df)
            selected_ids = set(st.session_state["selected_candidate_ids"])

            display_cols = matching.candidate_display_columns(show_df)
            candidate_table = show_df[display_cols].copy()
            candidate_table.insert(
                0,
                "Pilih",
                candidate_table[id_col].astype(str).isin(selected_ids),
            )

            edited_candidates = st.data_editor(
                candidate_table.style.apply(matching.highlight_candidate_status, axis=1),
                use_container_width=True,
                hide_index=True,
                disabled=[col for col in candidate_table.columns if col != "Pilih"],
                column_config={
                    "Pilih": st.column_config.CheckboxColumn(
                        "Pilih",
                        help="Centang kandidat yang ingin dikirim.",
                        default=False,
                    )
                },
                key=f"candidate_editor_{st.session_state['active_request_id']}_{top_n_label}",
            )

            visible_ids = set(candidate_table[id_col].astype(str))
            visible_selected_ids = set(
                edited_candidates.loc[edited_candidates["Pilih"], id_col].astype(str)
            )
            all_selected_ids = (selected_ids - visible_ids) | visible_selected_ids
            st.session_state["selected_candidate_ids"] = list(all_selected_ids)

            selected_candidates = detail_df.loc[
                detail_df[id_col].astype(str).isin(all_selected_ids),
                matching.candidate_display_columns(detail_df),
            ].copy()
            selected_candidates = selected_candidates.drop(
                columns=["Pilih"], errors="ignore"
            )

            a1, a2, a3 = st.columns([1, 1, 1])
            with a1:
                st.markdown(f"**{len(selected_candidates)} dari {tr_req['headcount']} kandidat terpilih**")
            with a2:
                if st.button(
                    "Reset kandidat terpilih",
                    use_container_width=True,
                    key=f"reset_candidates_{st.session_state['active_request_id']}",
                ):
                    metrics.reset_selected_candidates()
                    st.rerun()
            with a3:
                st.download_button(
                    "Export CSV kandidat terpilih",
                    data=matching.csv_download_bytes(selected_candidates),
                    file_name=f"kandidat_terpilih_{st.session_state['active_request_id']}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    disabled=selected_candidates.empty
                )

            if st.button(
                "Kirim kandidat",
                type="primary",
                use_container_width=True,
                disabled=selected_candidates.empty,
                key=f"send_candidates_{st.session_state['active_request_id']}",
            ):
                st.session_state["sent_candidates"][st.session_state["active_request_id"]] = (
                    selected_candidates.to_dict("records")
                )
                st.success(
                    f"{len(selected_candidates)} kandidat berhasil ditandai untuk dikirim."
                )

            sent_count = len(
                st.session_state["sent_candidates"].get(
                    st.session_state["active_request_id"], []
                )
            )
            if sent_count:
                st.caption(f"Terakhir dikirim: {sent_count} kandidat.")



