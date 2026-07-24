# pages/1_Beranda.py
# Owner: built last by whoever finishes first. Purpose: Action Queue (BT-02, BT-05 individual). See spec Section 6.1.
#
# Rules followed (kept consistent with pages/3_Monitoring.py and pages/4_Analitik.py):
# - No metric is recomputed here. Every number comes from core/metrics.py.
# - No CSV is read here. Data comes from core/loader + core/clean.
# - Category values come from core/schema.py, never raw strings.
# - Colors come from config.WARNA, no hex is written in this file.
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
import core  # noqa: F401
import config
import schema
from core import loader, clean, metrics
import components.html as H
import components.tables as T

WARNA = config.WARNA


# ---------------------------------------------------------------------------
# Data. Loaded and cleaned once by the cached loader.
# ---------------------------------------------------------------------------

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
    ),
    unsafe_allow_html=True,
)

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
