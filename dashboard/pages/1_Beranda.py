# pages/1_Beranda.py
<<<<<<< HEAD
# Owner: built last by whoever finishes first. Purpose: Action Queue (BT-02, BT-05 individual). See spec Section 6.1.
#
# Rules followed (kept consistent with pages/3_Monitoring.py and pages/4_Analitik.py):
=======
# Owner: Beranda builder (assembled last). Action Queue page.
# Spec Section 6.1 (BT-02 and BT-05 at the individual level).
# Answers: as CDC staff, what do I act on NOW, and show me the detail.
#
# Rules followed (same as Analitik):
>>>>>>> b641aa59e8e20ba35d351236f1c62a20cf83776b
# - No metric is recomputed here. Every number comes from core/metrics.py.
# - No CSV is read here. Data comes from core/loader + core/clean.
# - Category values come from core/schema.py, never raw strings.
# - Colors come from config.WARNA, no hex is written in this file.
<<<<<<< HEAD
# - Cards, badges, callouts, tables use HTML helpers from components/html.py.
#   The queue table and drill-down panel are built by components/tables.py.
#   Inputs (search, sort, segment buttons, dataframe selection) are native
#   Streamlit widgets.
#
# Layout: two stacked segments, not tabs - Kondisi Perusahaan and Perlu
# Tindakan Segera, separated by a divider. Kondisi Perusahaan is a scaffold
# placeholder for this pass (Section 6.1 point 1, owner-decided, comes
# later). Perlu Tindakan Segera is the full build of Section 6.1 points
# 2-6: 5 urgency segment cards, the queue table, the drill-down panel,
# action buttons, and the cross-link from Monitoring.

import streamlit as st

# Importing the core package runs core/__init__.py, which puts dashboard/ and
# dashboard/core/ on sys.path. That makes the plain imports below work whether
# this page is launched by streamlit run or imported directly.
=======
# - KPI cards, badges, callouts use HTML helpers from components/html.py.
#   The queue table is a native st.dataframe because it must support
#   on_select drill-down (spec render-path table). Inputs are native widgets.
#
# Build phase: barebones. Structure, real data, correct render path. Styling
# (CSS polish, the segment cards as cards) is a later pass.

import streamlit as st

# Importing core runs core/__init__.py, which fixes sys.path so the plain
# imports below work under streamlit run and under a direct import.
>>>>>>> b641aa59e8e20ba35d351236f1c62a20cf83776b
import core  # noqa: F401
import config
import schema
from core import loader, clean, metrics
<<<<<<< HEAD
import components.html as H
import components.tables as T
=======
from components import html as H
from components import styles as S
>>>>>>> b641aa59e8e20ba35d351236f1c62a20cf83776b

WARNA = config.WARNA


# ---------------------------------------------------------------------------
# Data. Loaded and cleaned once by the cached loader.
# ---------------------------------------------------------------------------

<<<<<<< HEAD
raw = loader.load_data()
data = clean.clean_data(raw)

tracking_student = data.tracking_student
status_student = data.status_student
student_all = data.student_all
ANCHOR = data.ANCHOR

st.set_page_config(page_title="Beranda SSDC", layout="wide")
st.title("Beranda")
st.caption(
    "Sebagai staf CDC, apa yang harus ditindak sekarang, dan detailnya. "
    "Data per " + str(ANCHOR.date()) + "."
)


# ===========================================================================
# SEGMEN 1 - KONDISI PERUSAHAAN (Section 6.1 point 1, owner-decided).
# Scaffold only for this pass. Filled in after Perlu Tindakan Segera.
# ===========================================================================

st.markdown("## Kondisi Perusahaan")
st.markdown(
    H.callout(
        "KPI ringkas kondisi CDC secara keseluruhan (Section 6.1 poin 1) "
        "menyusul di sini. Belum diisi pada tahap ini.",
        kind="muted",
=======
st.set_page_config(page_title="Beranda SSDC", layout="wide")
S.inject()

raw = loader.load_data()
data = clean.clean_data(raw)

ts = data.tracking_student
ss = data.status_student
sa = data.student_all
tc = data.tracking_company
co = data.company
st.markdown(
    H.page_header(
        "Beranda",
        "Antrean tindak lanjut. Paling mendesak di atas. Klik satu baris "
        "untuk melihat seluruh proses mahasiswa itu.",
        eyebrow="Antrean Aksi",
        stamp="Data per " + str(data.ANCHOR.date()),
>>>>>>> b641aa59e8e20ba35d351236f1c62a20cf83776b
    ),
    unsafe_allow_html=True,
)

<<<<<<< HEAD
st.markdown("---")


# ===========================================================================
# SEGMEN 2 - PERLU TINDAKAN SEGERA (Section 6.1 poin 2-6).
# ===========================================================================

st.markdown("## Perlu Tindakan Segera")
st.caption(
    "Klik satu kartu untuk memfilter antrean di bawah. Judul, jumlah, dan "
    "isi tabel mengikuti kartu yang dipilih."
)

# ---------------------------------------------------------------------------
# Segment definitions. Urgency order per Section 4.7: Ghosting -> FU 3 ->
# FU 1 + FU 2 -> Interview User + Final Interview -> Eligible belum dikirim.
# Card colors follow the same WARNA keys as everywhere else in the app
# (crit/warn/watch/hot/ok), not a page-specific palette.
# ---------------------------------------------------------------------------

SEGMENTS = {
    "ghosting": {
        "label": "Ghosting, ambang batas",
        "subtitle": ">4 minggu tanpa respons perusahaan",
        "stages": [schema.STAGE_GHOSTING],
        "accent": "crit",
    },
    "fu3": {
        "label": "FU 3, eskalasi terakhir",
        "subtitle": "Satu langkah sebelum ghosting",
        "stages": [schema.STAGE_FU3],
        "accent": "warn",
    },
    "fu12": {
        "label": "FU 1 & 2, menunggu",
        "subtitle": "Follow up berjalan, belum tuntas",
        "stages": [schema.STAGE_FU1, schema.STAGE_FU2],
        "accent": "watch",
    },
    "interview": {
        "label": "Interview, dekat placement",
        "subtitle": "Interview User & Final, jangan lepas",
        "stages": [schema.STAGE_INTERVIEW, schema.STAGE_FINAL],
        "accent": "hot",
    },
}
SEGMENT_ORDER = ["ghosting", "fu3", "fu12", "interview", "eligible"]

# Counts. Every count comes from a core/metrics.py mask. A card spanning two
# stages (FU1+FU2, Interview+Final) sums two mask counts here, the same
# pattern the Monitoring/Analitik definition footers use for "selisih".
segment_counts = {}
for _key, _seg in SEGMENTS.items():
    segment_counts[_key] = int(
        sum(
            int(metrics.stage_mask(tracking_student, s).sum())
            for s in _seg["stages"]
        )
    )
eligible_df_full = metrics.eligible_belum_dikirim(status_student, tracking_student)
segment_counts["eligible"] = len(eligible_df_full)

# ---------------------------------------------------------------------------
# Cross-link from Monitoring (Section 6.1 point 6). Consumed once. If the
# funnel stage Monitoring sent matches one of the 5 cards, select that card.
# Otherwise (Selecting, CDC Briefing, Study Case, Placement - funnel stages
# the 5 urgency cards do not cover) fall back to an ad hoc single-stage
# filter so the click-through still lands on the right rows.
# ---------------------------------------------------------------------------

if "active_segment" not in st.session_state:
    st.session_state["active_segment"] = "ghosting"

_cross = st.session_state.pop("beranda_segment", None)
if _cross and _cross.get("stage"):
    _matched_key = None
    for key, seg in SEGMENTS.items():
        if _cross["stage"] in seg["stages"]:
            _matched_key = key
            break
    if _matched_key:
        st.session_state["active_segment"] = _matched_key
    else:
        st.session_state["active_segment"] = "custom"
        st.session_state["custom_stage"] = _cross["stage"]

active = st.session_state["active_segment"]
custom_stage = st.session_state.get("custom_stage") if active == "custom" else None
if active == "custom" and not custom_stage:
    # Stale state with nothing to show (e.g. custom_stage never got set).
    # Fall back to the most urgent card rather than crash on a missing key.
    active = "ghosting"
    st.session_state["active_segment"] = "ghosting"

# ---------------------------------------------------------------------------
# 5 segment cards. HTML card is presentational (components/html.py). The
# native button underneath is what actually drives the filter, per the
# project's render-path rule: inputs are always native Streamlit widgets.
# ---------------------------------------------------------------------------

card_cols = st.columns(5)
for col, key in zip(card_cols, SEGMENT_ORDER):
    with col:
        if key == "eligible":
            title = "Eligible, belum dikirim"
            subtitle = "Siap kirim, punya CV, belum diproses"
            accent = "ok"
        else:
            seg = SEGMENTS[key]
            title, subtitle, accent = seg["label"], seg["subtitle"], seg["accent"]
        st.markdown(
            H.kpi_card(
                title, H._fmt_id(segment_counts[key]), subtitle,
                accent=WARNA[accent], big=True,
            ),
            unsafe_allow_html=True,
        )
        is_active = active == key
        if st.button(
            "Sedang ditampilkan" if is_active else "Tampilkan",
            key="seg_btn_" + key,
            use_container_width=True,
            disabled=is_active,
        ):
            st.session_state["active_segment"] = key
            st.session_state.pop("custom_stage", None)
            st.rerun()

# ---------------------------------------------------------------------------
# Build the active queue dataframe. Eligible has a different column shape
# than the stage-based segments (Section 6.1 point 2).
# ---------------------------------------------------------------------------

if active == "eligible":
    active_title = "Eligible, belum dikirim"
    base_df = T.build_eligible_queue(eligible_df_full, student_all)
    search_cols = ["NIM", "Mahasiswa", "Prodi"]
elif active == "custom":
    active_title = "Tahap: " + str(custom_stage)
    subset = tracking_student[tracking_student["progress_student"] == custom_stage]
    base_df = T.build_stage_queue(subset, student_all, ANCHOR)
    search_cols = ["NIM", "Mahasiswa", "Perusahaan & Posisi"]
else:
    seg = SEGMENTS[active]
    active_title = seg["label"]
    subset = tracking_student[tracking_student["progress_student"].isin(seg["stages"])]
    base_df = T.build_stage_queue(subset, student_all, ANCHOR)
    search_cols = ["NIM", "Mahasiswa", "Perusahaan & Posisi"]

total_rows = len(base_df)

st.markdown("### " + active_title)
col_search, col_sort = st.columns([2, 1])
with col_search:
    query = st.text_input(
        "Cari NIM / nama / perusahaan", key="beranda_search",
        placeholder="Cari NIM / nama / perusahaan", label_visibility="collapsed",
    )
with col_sort:
    has_diam = "Diam (hari)" in base_df.columns
    if has_diam:
        sort_label = st.selectbox(
            "Urutkan", ["Paling lama diam", "Paling baru diam"],
            key="beranda_sort", label_visibility="collapsed",
        )
    else:
        sort_label = None
        st.caption("Urut: nama")

view_df = base_df
if query:
    mask = None
    for c in search_cols:
        col_mask = view_df[c].astype(str).str.contains(query, case=False, na=False)
        mask = col_mask if mask is None else (mask | col_mask)
    view_df = view_df[mask]

if sort_label == "Paling lama diam":
    view_df = view_df.sort_values("Diam (hari)", ascending=False)
elif sort_label == "Paling baru diam":
    view_df = view_df.sort_values("Diam (hari)", ascending=True)

st.caption(
    active_title + " · menampilkan " + H._fmt_id(len(view_df)) + " dari "
    + H._fmt_id(total_rows)
)

QUEUE_HEIGHT = 560  # shared height: left table and right panel read as one block.

col_table, col_panel = st.columns([2.4, 1.3])

with col_table:
    display_cols = [c for c in view_df.columns if c != "NIM"]
    column_config = {}
    if "Kontak" in view_df.columns:
        column_config["Kontak"] = st.column_config.LinkColumn(
            "Kontak", display_text="Hubungi"
        )
    # selection_mode="single-cell", not "single-row": row-selection modes
    # always render a checkbox column (implies multi-select), which is
    # misleading here since only one profile is ever shown at a time.
    # Clicking any cell still selects its whole row for the panel below.
    event = st.dataframe(
        view_df,
        column_order=display_cols,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        height=QUEUE_HEIGHT,
        on_select="rerun",
        selection_mode="single-cell",
        key="beranda_queue_df",
    )

with col_panel:
    if view_df.empty:
        st.markdown(
            H.callout(
                "Tidak ada baris pada segmen/pencarian ini.", kind="muted",
            ),
            unsafe_allow_html=True,
        )
    elif not event.selection.cells:
        st.markdown(
            H.callout(
                "Klik satu baris di antrean untuk melihat profil lengkap "
                "mahasiswa dan semua proses seleksinya.",
                kind="muted",
            ),
            unsafe_allow_html=True,
        )
    else:
        row_idx = event.selection.cells[0][0]
        selected_nim = view_df.iloc[row_idx]["NIM"]
        T.render_drilldown_panel(
            selected_nim, status_student, tracking_student, student_all
        )
=======

# ===========================================================================
# PART 1. Compact KPIs. Operational first: what needs action, plus context.
# ===========================================================================

seg_counts = metrics.beranda_segment_counts(ts, ss)
n_ghosting = seg_counts[schema.SEG_GHOSTING]
n_draft = len(metrics.draft_requests(tc))
n_placed_student = metrics.success_numerator_per_student(ts)
# Total tracking queue = the four active segments (not the eligible students).
n_queue = (
    seg_counts[schema.SEG_GHOSTING] + seg_counts[schema.SEG_FU3]
    + seg_counts[schema.SEG_FU12] + seg_counts[schema.SEG_INTERVIEW]
)

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(
        H.kpi_card("Ghosting aktif", H._fmt_id(n_ghosting),
                   "proses menunggu, perlu tindakan", accent=WARNA["crit"]),
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        H.kpi_card("Proses antre tindak lanjut", H._fmt_id(n_queue),
                   "total 4 segmen aktif", accent=WARNA["warn"]),
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        H.kpi_card("Permintaan belum digarap", H._fmt_id(n_draft),
                   "status Draft, belum dikirim", accent=WARNA["warn"]),
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        H.kpi_card("Mahasiswa ditempatkan", H._fmt_id(n_placed_student),
                   "hasil positif sejauh ini", accent=WARNA["ok"]),
        unsafe_allow_html=True,
    )


# ===========================================================================
# PART 2. Urgency segment selection. Native buttons are the event bridge.
# Styling into cards happens in the styling pass, so this is the final path,
# not throwaway. Clicking a segment filters the queue below.
# ===========================================================================

st.markdown("### Pilih segmen")

# Default to the most urgent segment. A cross-link from Monitoring may have
# already written st.session_state['beranda_segment'] (spec 6.1 point 6).
if "beranda_segment" not in st.session_state:
    st.session_state["beranda_segment"] = schema.BERANDA_SEGMEN_ORDER[0]

seg_cols = st.columns(len(schema.BERANDA_SEGMEN_ORDER))
for i, seg in enumerate(schema.BERANDA_SEGMEN_ORDER):
    with seg_cols[i]:
        selected = st.session_state["beranda_segment"] == seg
        label = seg + "  (" + H._fmt_id(seg_counts[seg]) + ")"
        if st.button(label, key="seg_btn_" + seg, use_container_width=True,
                     type="primary" if selected else "secondary"):
            st.session_state["beranda_segment"] = seg
            st.rerun()

active_seg = st.session_state["beranda_segment"]


# ===========================================================================
# PART 3 and 4. Queue table (left) and drill-down panel (right).
# ===========================================================================

# Session store for "Tandai ditindak". Session only, lost on refresh.
if "ditindak" not in st.session_state:
    st.session_state["ditindak"] = set()


def _build_queue_display(active_seg):
    """Assemble the display dataframe for the active segment.

    Tracking segments share one column shape. The Eligible segment has a
    different shape (program, IPK, domicile, CV instead of stage and idle).
    Returns (display_df, is_eligible). display_df keeps a NIM column so a
    selected row maps back to a student.
    """
    if active_seg == schema.SEG_ELIGIBLE:
        elig = metrics.eligible_belum_dikirim(ss, ts).copy()
        elig = elig.merge(sa[["NIM", "hp"]], on="NIM", how="left")
        elig = elig.reset_index(drop=True)
        disp = elig[[
            "NIM", "nama", "program_studi", "IPK", "domisili", "CV", "hp",
        ]].copy()
        disp["Mahasiswa"] = disp["nama"] + " (" + disp["NIM"] + ")"
        disp["Kontak"] = disp["hp"].map(H.wa_url)
        view = disp[[
            "Mahasiswa", "program_studi", "IPK", "domisili", "CV", "Kontak",
        ]].rename(columns={
            "program_studi": "Program", "domisili": "Domisili",
        })
        return disp, view, True

    q = metrics.beranda_queue(ts, data.ANCHOR)
    q = q[q["segmen"] == active_seg].copy()
    q = q.merge(sa[["NIM", "hp"]], on="NIM", how="left").reset_index(drop=True)
    q["Mahasiswa"] = q["student_name"] + " (" + q["NIM"] + ")"
    q["Perusahaan & posisi"] = q["company"] + " - " + q["position"]
    q["Kontak"] = q["hp"].map(H.wa_url)
    view = q[[
        "Mahasiswa", "Perusahaan & posisi", "progress_student", "diam_hari",
        "Kontak",
    ]].rename(columns={
        "progress_student": "Tahap", "diam_hari": "Diam (hari)",
    })
    return q, view, False


disp_full, view, is_eligible = _build_queue_display(active_seg)

# Search filter over NIM, name, and company (native input).
cari = st.text_input("Cari NIM, nama, atau perusahaan", key="cari_queue")
if cari.strip():
    key = cari.strip().lower()
    hay = disp_full["NIM"].astype(str).str.lower()
    hay = hay + " " + disp_full["Mahasiswa"].str.lower()
    if not is_eligible:
        hay = hay + " " + disp_full["Perusahaan & posisi"].str.lower()
    keep = hay.str.contains(key, na=False)
    disp_full = disp_full[keep].reset_index(drop=True)
    view = view.loc[disp_full.index].reset_index(drop=True)

left, right = st.columns([3, 2])

with left:
    st.markdown("#### " + active_seg + "  (" + H._fmt_id(len(view)) + " baris)")
    link_col = st.column_config.LinkColumn("Kontak", display_text="WhatsApp")
    event = st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={"Kontak": link_col},
        height=420,
        key="queue_df",
    )


# ---------------------------------------------------------------------------
# Drill-down panel. The team differentiator: one student, every process.
# ---------------------------------------------------------------------------

with right:
    st.markdown("#### Detail mahasiswa")
    sel_rows = event.selection.rows if event and event.selection else []
    if not sel_rows:
        st.caption("Klik satu baris di antrean untuk melihat profil dan semua "
                   "prosesnya.")
    else:
        idx = sel_rows[0]
        nim = str(disp_full.iloc[idx]["NIM"])

        prof_rows = ss[ss["NIM"] == nim]
        if len(prof_rows) == 0:
            st.warning("Profil status_student tidak ditemukan untuk NIM ini.")
        else:
            prof = prof_rows.iloc[0]

            # Placed-elsewhere callout comes first: it changes the action.
            placements = metrics.student_placements(ts, nim)
            if len(placements) > 0:
                perusahaan = ", ".join(sorted(set(placements["company"])))
                st.markdown(
                    H.callout(
                        "Sudah placed di " + perusahaan + ". Konfirmasi dulu "
                        "sebelum follow up, kemungkinan mahasiswa ini sudah "
                        "diterima di tempat lain.",
                        kind="warn", title="Perhatian",
                    ),
                    unsafe_allow_html=True,
                )

            # Profile block.
            cv_badge = H.badge(
                "CV ada" if prof["CV"] == schema.CV_ADA else "tanpa CV",
                "ok" if prof["CV"] == schema.CV_ADA else "warn",
            )
            tools = prof.get("tools_list") or []
            tools_txt = ", ".join(tools) if len(tools) else "tidak tercatat"
            ipk_txt = "-" if prof["IPK"] is None else str(prof["IPK"])
            st.markdown(
                H.callout(
                    prof["nama"] + " (" + nim + ")\n"
                    "Program: " + str(prof["program_studi"]) + "\n"
                    "IPK: " + ipk_txt + "  |  Domisili: "
                    + str(prof["domisili"]) + "\n"
                    "Tools: " + tools_txt,
                    kind="accent", title="Profil",
                ).replace("\n", "<br>"),
                unsafe_allow_html=True,
            )
            st.markdown(cv_badge, unsafe_allow_html=True)

            # All processes across every company (the differentiator).
            st.markdown("**Semua proses mahasiswa ini**")
            proc = metrics.student_processes(ts, nim)[[
                "company", "position", "progress_student", "rejection",
                "last_update",
            ]].rename(columns={
                "company": "Perusahaan", "position": "Posisi",
                "progress_student": "Tahap", "rejection": "Status",
                "last_update": "Update terakhir",
            })
            st.dataframe(proc, use_container_width=True, hide_index=True)

            # Actions.
            hp_rows = sa[sa["NIM"] == nim]
            wa = H.wa_url(hp_rows.iloc[0]["hp"]) if len(hp_rows) else ""
            a1, a2 = st.columns(2)
            with a1:
                if wa:
                    st.link_button("Hubungi via WhatsApp", wa,
                                   use_container_width=True)
                else:
                    st.button("Hubungi via WhatsApp", disabled=True,
                              use_container_width=True,
                              help="Nomor tidak tersedia")
            with a2:
                if st.button("Tandai ditindak", key="tandai_" + nim,
                             use_container_width=True):
                    st.session_state["ditindak"].add(nim)

            if nim in st.session_state["ditindak"]:
                st.caption("Ditandai ditindak. Catatan: tidak tersimpan "
                           "permanen, hilang saat halaman dimuat ulang.")


# ===========================================================================
# Footer. Keep the session-only caveat and the placement definition visible.
# ===========================================================================

st.markdown("---")
st.caption(
    "Antrean memakai label progress_student apa adanya (bukan hitung ulang), "
    "sesuai aturan follow-up. Segmen diurut dari yang paling mendesak, dan di "
    "dalam satu segmen diurut dari yang paling lama diam. Tanda 'ditindak' "
    "hanya sesi ini, tidak tersimpan permanen."
)
>>>>>>> b641aa59e8e20ba35d351236f1c62a20cf83776b
