# pages/2_Matching.py
# Owner: Mutia. Purpose: Matching (BT-01, BT-03, BT-06). See spec Section 6.2.

import os

import pandas as pd
import streamlit as st
from streamlit_searchbox import st_searchbox

import config
from core import clean, loader, metrics, schema, matching
from components import html as H


WARNA = config.WARNA


# Data. Loaded and cleaned once by the cached loader. Page config, global CSS,
# and the shared sidebar are set once by app.py (the st.navigation controller).

raw = loader.load_data()
data = clean.clean_data(raw)

ts = data.tracking_student
tc = data.tracking_company
ss = data.status_student
sa = data.student_all
co = data.company
tr = data.talent_request
ANCHOR = data.ANCHOR

# Date filter comes from the shared sidebar (set in app.py). On Matching the
# request list is filtered by request_date (spec Section 5.4).
periode_filter = st.session_state.get("rentang_periode")
if periode_filter:
    start, end = periode_filter
    tc = tc[(tc["request_date"] >= start) & (tc["request_date"] <= end)]


def _engine_source_version():
    """Fingerprint of the engine source, used as a cache key.

    st.cache_resource does not notice that core/matching.py changed, so a
    running app kept serving an engine built from older code: after the
    cross-request lookup gained a "tahap" field, the cached engine still
    returned entries without it and the column rendered empty everywhere.
    Keying on the file's modification time rebuilds the engine whenever the
    engine code changes, and costs one stat() call per rerun.
    """
    try:
        return os.path.getmtime(matching.__file__)
    except OSError:
        return 0.0


@st.cache_resource(show_spinner="Memproses pencarian...", max_entries=1,
                   ttl=1800)
def _get_matching_engine(source_version):
    """Build and precompute MatchingEngine once per session.

    source_version is not read inside; it exists so a change to the engine
    source invalidates this cache (see _engine_source_version).

    Cached as a resource (not cache_data): precompute() builds the tool
    lexicon and historical knowledge dictionary from the full student and
    tracking tables, expensive to redo on every widget interaction. Fed the
    same already-cleaned dataframes every other section of this page uses,
    not a second raw CSV read.
    """
    # Bounded on purpose. The precompute builds about fourteen per-student
    # dicts over 25.000 students and costs roughly 140 MB resident, which is
    # the single largest allocation in the app. cache_resource never evicts by
    # default, so without max_entries/ttl that 140 MB stayed for the life of
    # the process even after the user left the Matching page, and on Streamlit
    # Community Cloud (about 1 GB) that is what pushes the app over its limit.
    # max_entries=1 keeps exactly one engine; ttl releases it once idle.

    # clean_data() is itself cached now, so this returns the same CleanData
    # instance the page body already holds; no second read or clean happens.
    cleaned = clean.clean_data(loader.load_data())
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


def _breakdown_text(row):
    """Ringkasan teks per komponen skor untuk satu kandidat.

    Reshape murni untuk tampilan: seluruh angka diambil apa adanya dari
    kolom hasil engine.recommend() (Program Study Score, Tools Cocok,
    Coverage Tools, IPK, Domisili Sama Kantor). Tidak menghitung ulang atau
    mengubah arti metrik apa pun. Contoh keluaran:
    "prodi ok, tools 2/3, IPK 3,61, sekota".
    """
    parts = []

    # Prodi: Program Study Score sudah 0-100. 100 berarti prodi persis cocok.
    prodi_score = float(row.get("Program Study Score", 0) or 0)
    if prodi_score >= 100:
        parts.append("prodi cocok")
    elif prodi_score >= 35:
        parts.append("prodi mirip")
    else:
        parts.append("prodi beda")

    # Tools: jumlah tools cocok / total tools yang diminta (dari coverage).
    cocok = int(row.get("Tools Cocok", 0) or 0)
    coverage = float(row.get("Coverage Tools", 0) or 0)
    total_tools = round(cocok / (coverage / 100)) if coverage > 0 else 0
    if total_tools > 0:
        parts.append(f"{cocok}/{total_tools} keahlian cocok")
    else:
        parts.append("keahlian tidak tercatat")

    # IPK: dua desimal, koma desimal Indonesia.
    ipk = row.get("IPK", None)
    if ipk is not None and not pd.isna(ipk):
        parts.append("IPK " + f"{float(ipk):.2f}".replace(".", ","))

    # Domisili: sekota bila domisili sama dengan kota kantor.
    if bool(row.get("Domisili Sama Kantor", False)):
        parts.append("sekota")

    return ", ".join(parts)


st.markdown(
    H.page_header(
        "Pencocokan Kandidat",
        "Cocokkan permintaan perusahaan dengan "
        "mahasiswa yang paling sesuai.",
    ),
    unsafe_allow_html=True,
)


st.session_state.setdefault("request_table_version", 0)
st.session_state.setdefault("selected_candidate_ids", [])
st.session_state.setdefault("active_request_id", None)

# cell matching
c1, c2 = st.columns([1.5, 3.2]) # bagi kolom

draft_req = metrics.draft_requests(tc).copy() # ambil draft request dari tracking company
draft_req["label"] = (draft_req["nama_perusahaan"]+" - "+draft_req["posisi"]) # label searching
draft_req["days_left"] = (ANCHOR - draft_req["request_date"]).dt.days
req_days = metrics.request_age_days(tc, ANCHOR)
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


# Kolom tabel daftar request. Header mentah (nama_perusahaan, posisi, ...)
# diberi label Indonesia yang rapi lewat column_config di st.dataframe.
REQ_TABLE_COLS = {
    "nama_perusahaan": "Perusahaan",
    "posisi": "Posisi",
    "jumlah_permintaan": "Kebutuhan",
    "jumlah_dikirimkan": "Terkirim",
    "days_left": "Umur (hari)",
}
c1_cols = list(REQ_TABLE_COLS.keys())


# design kolom 1
with c1:
    with st.container(height=760):
        cel1, cel2 = st.columns([1, 1])
        with cel1:
            st.markdown("**Permintaan terbuka**")
        with cel2:
            st.markdown(
                f"<div style='text-align: right;'><b>{str(n_req)}</b> belum dikirimkan</div>",
                unsafe_allow_html=True
            )

        # search box
        selected = st_searchbox(
            search_function = search_request,
            placeholder = "Cari perusahaan atau posisi",
            key = "req_search"
        )

        # urutan
        option = st.selectbox(
            "Urutkan",
            ["Terbaru", "Terlama", "Kebutuhan terbanyak", "Kebutuhan tersedikit"],
            key = "req_sort"
        )

        req_filtered = draft_req

        # sort
        if option == "Terbaru":
            req_sorted = req_filtered.sort_values("request_date", ascending = False)
        elif option == "Terlama":
            req_sorted = req_filtered.sort_values("request_date", ascending = True)
        elif option == "Kebutuhan terbanyak":
            req_sorted = req_filtered.sort_values("jumlah_permintaan", ascending = False)
        else:
            req_sorted = req_filtered.sort_values("jumlah_permintaan", ascending = True)

        # Permintaan yang dipilih lewat kotak cari menyaring tabel, bukan
        # sekadar dinaikkan ke atas. Sebelumnya seluruh 598 baris tetap
        # tampil dengan yang cocok di baris pertama, sehingga hasil pencarian
        # tidak terlihat seperti hasil pencarian.
        if selected:
            req_show = req_sorted[req_sorted["label"] == selected].reset_index(
                drop=True
            )
        else:
            req_show = req_sorted

        # tabel request, header mentah diganti label Indonesia
        event = st.dataframe(
            req_show[c1_cols],
            use_container_width = True,
            hide_index = True,
            on_select = "rerun",
            selection_mode = 'single-row',
            column_config = {
                # Lebar diatur per kolom supaya panel kiri yang sempit tidak
                # perlu digeser mendatar: dua kolom teks dapat porsi utama,
                # tiga kolom angka dipersempit. Sebelumnya kelimanya memakai
                # lebar otomatis dan kolom Perusahaan ikut terpotong.
                "nama_perusahaan": st.column_config.TextColumn(
                    label="Perusahaan", width="medium"),
                "posisi": st.column_config.TextColumn(
                    label="Posisi", width="medium"),
                "jumlah_permintaan": st.column_config.NumberColumn(
                    label="Butuh", width="small"),
                "jumlah_dikirimkan": st.column_config.NumberColumn(
                    label="Terkirim", width="small"),
                "days_left": st.column_config.NumberColumn(
                    label="Umur (hari)", width="small"),
            },
        )

        if st.button(
            "Reset permintaan terpilih",
            use_container_width=True,
            key="reset_selected_request",
        ):
            metrics.reset_selected_request()
            st.rerun()


# design kolom 2
with c2:
    if not event.selection.rows:
        st.info(
            "Pilih satu permintaan untuk melihat detailnya "
            "dan rekomendasi mahasiswa yang sesuai."
        )
    else:
        idx = event.selection.rows[0]
        req = req_show.iloc[idx]
        tr_req = tr.loc[tr['id_talent_req'] == req['id_talent_req']].iloc[0]
        co_req = co.loc[co['id_company'] == req['id_company']].iloc[0]
        tid = str(req["id_talent_req"])

        # -- Header permintaan: posisi jadi judul utama, kode jadi metadata --
        st.markdown(
            f"<div style='color:{WARNA['muted']};font-size:0.78rem;"
            f"letter-spacing:0.04em;'>Kode permintaan {H._esc(str(req['id_talent_req']))}"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-size:1.6rem;font-weight:800;line-height:1.15;"
            f"color:{WARNA['navy']};'>{H._esc(str(tr_req['nama_posisi']))}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-size:1rem;color:{WARNA['ink2']};margin-bottom:2px;'>"
            f"{H._esc(str(req['nama_perusahaan']))}</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"{tr_req['renumerasi']} | Durasi penempatan: {tr_req['durasi']}"
        )

        # -- Baris atribut permintaan: tiap nilai diberi label kecil --
        def _attr(label, value):
            return (
                f"<div style='margin-bottom:6px;'>"
                f"<div style='color:{WARNA['muted']};font-size:0.7rem;"
                f"text-transform:uppercase;letter-spacing:0.04em;'>{H._esc(label)}</div>"
                f"<div style='color:{WARNA['ink']};font-size:0.9rem;font-weight:600;'>"
                f"{H._esc(str(value))}</div></div>"
            )

        prodi_list = req['bidang_studi_dicari_list']
        prodi_text = ", ".join(prodi_list) if prodi_list else "Semua program studi"

        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown(_attr("Jenis", tr_req['jenis_penempatan']), unsafe_allow_html=True)
            st.markdown(_attr("Skema kerja", tr_req["working_arrangement_detail"]), unsafe_allow_html=True)
        with a2:
            st.markdown(_attr("Kebutuhan", f"{tr_req['headcount']} orang"), unsafe_allow_html=True)
            st.markdown(_attr("Lokasi", co_req["kota"]), unsafe_allow_html=True)
        with a3:
            st.markdown(
                _attr("Semester minimum", f"min. semester {tr_req['minimum_semester']}"),
                unsafe_allow_html=True,
            )
            st.markdown(_attr("Program studi", prodi_text), unsafe_allow_html=True)

        st.caption(f"Kehalian yang dibutuhkan: {tr_req['deskripsi_requirement']}")

        st.divider()

        # -- Panel bobot slider (Section 4.9) --
        w1, w2 = st.columns([3, 1])
        with w1:
            st.markdown("**Bobot penilaian**")
        with w2:
            if st.button(
                "Kembalikan ke bobot awal",
                use_container_width = True,
                key = f"reset_weight_{tid}",
            ):
                metrics.reset_matching_weights()
                st.rerun()

        if st.session_state["active_request_id"] != tid:
            st.session_state["active_request_id"] = tid
            st.session_state["selected_candidate_ids"] = []

        engine = _get_matching_engine(_engine_source_version())

        bw1, bw2, bw3, bw4, bw5, bw6 = st.columns(6)
        with bw1:
            bobot_tools = st.slider(
                "Keahlian", 0, 100, metrics.default_weight_percent("tool_match"),
                key="bobot_tool_match",
            )
        with bw2:
            bobot_prodi = st.slider(
                "Program studi", 0, 100, metrics.default_weight_percent("program_study"),
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
                "Domisili", 0, 100, metrics.default_weight_percent("location"),
                key="bobot_location",
            )
        with bw6:
            bobot_preferensi = st.slider(
                "Preferensi penempatan", 0, 100,
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

        st.divider()

        # -- Tabel kandidat --
        st.markdown("**Kandidat yang sesuai**")
        st.caption("Kandidat yang tidak memenuhi semester minimum tidak ditampilkan.")

        if rec_result.empty:
            st.markdown(
                H.callout(
                    "Tidak ada mahasiswa yang memenuhi syarat untuk permintaan ini.",
                    kind="watch",
                ),
                unsafe_allow_html=True,
            )
        else:
            detail_df = rec_result

            f1, f2 = st.columns([1, 1.4])
            with f1:
                portfolio_filter = st.radio(
                    "Filter portofolio",
                    ["Semua", "Hanya yang ada portofolio"],
                    horizontal=True,
                    key=f"portfolio_filter_{tid}",
                )
            with f2:
                requested_programs = matching.requested_program_options(req)
                program_filter_options = ["Semua program studi"] + requested_programs
                selected_program_filter = st.selectbox(
                    "Filter program studi",
                    program_filter_options,
                    key=f"program_filter_{tid}",
                )

            filtered_detail = detail_df.copy()
            if portfolio_filter == "Hanya yang ada portofolio":
                filtered_detail = filtered_detail[filtered_detail["Punya Portofolio"]]
            if selected_program_filter != "Semua program studi":
                filtered_detail = filtered_detail[
                    filtered_detail["Program Studi"].astype(str).str.lower()
                    == str(selected_program_filter).lower()
                ]

            top_n_label = st.selectbox(
                "Tampilkan",
                ["10 teratas", "25 teratas", "50 teratas", "100 teratas", "Semua"],
                key="matching_top_n",
            )
            n_map = {"10 teratas": 10, "25 teratas": 25, "50 teratas": 50,
                     "100 teratas": 100, "Semua": None}
            n_show = n_map[top_n_label]
            show_df = filtered_detail if n_show is None else filtered_detail.head(n_show)

            if show_df.empty:
                st.caption("Tidak ada kandidat yang sesuai dengan filter tabel.")

            id_col = matching.candidate_id_column(show_df)
            selected_ids = set(st.session_state["selected_candidate_ids"])

            # -- Bangun tabel tampilan: skor, breakdown per komponen, flag --
            # Reshape murni untuk tampilan. Angka tetap dari engine.recommend();
            # tidak ada metrik yang dihitung ulang atau diubah artinya di sini.
            display = pd.DataFrame(index=show_df.index)
            display[id_col] = show_df[id_col].astype(str)
            display["Nama"] = show_df["Nama Mahasiswa"]
            display["Program studi"] = show_df["Program Studi"]
            display["Skor akhir"] = show_df["Total Skor (Dinormalisasi)"]
            display["IPK"] = show_df["IPK"]
            # Breakdown komponen: satu kolom teks ringkas per kandidat, dari
            # angka komponen yang sudah dihitung engine (Program Study Score,
            # Tools Cocok/Coverage, IPK, Domisili Sama Kantor).
            display["Rincian skor"] = [
                _breakdown_text(r) for _, r in show_df.iterrows()
            ]
            display["Tools cocok"] = show_df["Matched Tools"]
            # Flag "proses lain": aktif bila kandidat masih ada di request lain.
            display["Proses lain"] = show_df["Jumlah Request Lain"] > 0
            # Status CV, dibaca langsung sebagai "Ada" atau "Tidak" (bukan
            # centang terbalik yang harus ditafsirkan dulu oleh pembaca).
            display["CV"] = (
                show_df["CV"].astype(str).str.strip()
                .eq(schema.CV_ADA)
                .map({True: "Ada", False: "Tidak"})
            )
            # Status portofolio, dibaca sama seperti kolom CV. Kolom ini ada
            # supaya filter portofolio di atas tabel punya umpan balik yang
            # terlihat: tanpa kolom ini, menyalakan filter hanya memangkas
            # jumlah baris tanpa pembaca bisa memastikan alasannya.
            display["Portofolio"] = (
                show_df["Punya Portofolio"]
                .astype(bool)
                .map({True: "Ada", False: "Tidak"})
            )

            display.insert(
                0,
                "Pilih",
                display[id_col].astype(str).isin(selected_ids),
            )

            edited_candidates = st.data_editor(
                display,
                use_container_width=True,
                hide_index=True,
                disabled=[col for col in display.columns if col != "Pilih"],
                column_config={
                    "Pilih": st.column_config.CheckboxColumn(
                        "Pilih",
                        default=False,
                    ),
                    "Skor akhir": st.column_config.NumberColumn(
                        "Skor akhir", format="%.1f",
                        help="Skor 0-100 relatif antar kandidat untuk permintaan ini.",
                    ),
                    "IPK": st.column_config.NumberColumn("IPK", format="%.2f"),
                    "Rincian skor": st.column_config.TextColumn(
                        "Rincian skor", width="large",
                    ),
                    "Proses lain": st.column_config.CheckboxColumn(
                        "Proses lain",
                        help="Kandidat sedang mengikuti permintaan lain yang masih aktif.",
                    ),
                    "CV": st.column_config.TextColumn(
                        "CV", width="small",
                        help="Apakah kandidat sudah melampirkan CV.",
                    ),
                    "Portofolio": st.column_config.TextColumn(
                        "Portofolio", width="small",
                        help="Apakah kandidat sudah melampirkan portofolio.",
                    ),
                },
                key=f"candidate_editor_{tid}_{top_n_label}",
            )

            visible_ids = set(display[id_col].astype(str))
            visible_selected_ids = set(
                edited_candidates.loc[edited_candidates["Pilih"], id_col].astype(str)
            )
            all_selected_ids = (selected_ids - visible_ids) | visible_selected_ids
            st.session_state["selected_candidate_ids"] = list(all_selected_ids)

            # -- Permintaan lain yang diikuti kandidat yang DICENTANG --
            # Sebelumnya bagian ini punya dropdown sendiri yang mengabaikan
            # centang di tabel, sehingga pengguna harus memilih nama untuk
            # kedua kalinya. Sekarang isinya mengikuti kandidat yang sudah
            # dicentang: mencentang satu nama langsung memunculkan riwayatnya.
            checked_with_other = filtered_detail[
                filtered_detail[id_col].astype(str).isin(all_selected_ids)
                & (filtered_detail["Jumlah Request Lain"] > 0)
            ]

            if all_selected_ids and not checked_with_other.empty:
                nama_lookup = dict(zip(
                    checked_with_other[id_col].astype(str),
                    checked_with_other["Nama Mahasiswa"],
                ))
                with st.expander(
                    "Permintaan lain yang sedang diikuti kandidat tercentang "
                    f"({len(checked_with_other)} kandidat)",
                    expanded=True,
                ):
                    for nim_key, nama in nama_lookup.items():
                        other_reqs = engine.other_requests(nim_key, exclude_tid=tid)
                        if not other_reqs:
                            continue
                        st.markdown(f"**{nama}** ({nim_key})")
                        st.markdown(
                            H.read_only_table(
                                ["Perusahaan", "Posisi", "Tahap saat ini",
                                 "Tanggal dikirim"],
                                [
                                    [
                                        r["perusahaan"], r["posisi"],
                                        r.get("tahap") or "-",
                                        "-" if pd.isna(r["tanggal"])
                                        else H.tanggal_id(
                                            pd.Timestamp(r["tanggal"]).date()
                                        ),
                                    ]
                                    for r in other_reqs
                                ],
                                align=["left", "left", "left", "left"],
                            ),
                            unsafe_allow_html=True,
                        )
            elif all_selected_ids:
                st.caption(
                    "Kandidat yang dicentang tidak sedang mengikuti "
                    "permintaan lain."
                )

            # -- Kandidat terpilih dan aksi akhir --
            selected_export = detail_df.loc[
                detail_df[id_col].astype(str).isin(all_selected_ids),
                matching.candidate_display_columns(detail_df),
            ].copy()

            nim_list = detail_df.loc[
                detail_df[id_col].astype(str).isin(all_selected_ids), id_col
            ].astype(str).tolist()

            st.markdown(
                f"**{len(nim_list)} dari {tr_req['headcount']} dipilih.**"

            )

            act1, act2, act3 = st.columns([1.2, 1, 1])
            with act1:
                if st.button(
                    "Reset kandidat terpilih",
                    use_container_width=True,
                    key=f"reset_candidates_{tid}",
                ):
                    metrics.reset_selected_candidates()
                    st.rerun()
            with act2:
                # "Salin daftar NIM": tampilkan NIM siap salin (dashboard tidak
                # punya mekanisme kirim, CDC menyalin ke sistem mereka sendiri).
                if st.button(
                    "Salin daftar NIM",
                    use_container_width=True,
                    disabled=not nim_list,
                    key=f"copy_nim_{tid}",
                ):
                    st.session_state[f"show_nim_{tid}"] = True
            with act3:
                st.download_button(
                    "Ekspor CSV",
                    data=matching.csv_download_bytes(selected_export),
                    file_name=f"kandidat_terpilih_{tid}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    disabled=selected_export.empty,
                )

            if st.session_state.get(f"show_nim_{tid}") and nim_list:
                st.code("\n".join(nim_list), language=None)