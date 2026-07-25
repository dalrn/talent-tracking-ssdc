# pages/1_Beranda.py
# Owner: Beranda builder (assembled last). Action Queue page.
# Spec Section 6.1 (BT-02 and BT-05 at the individual level).
# Answers: as CDC staff, what do I act on NOW, and show me the detail.
#
# Rules followed (same as Analitik):
# - No metric is recomputed here. Every number comes from core/metrics.py.
# - No CSV is read here. Data comes from core/loader + core/clean.
# - Category values come from core/schema.py, never raw strings.
# - Colors come from config.WARNA, no hex is written in this file.
# - KPI cards, badges, callouts use HTML helpers from components/html.py.
#   The queue table is a native st.dataframe because it must support
#   on_select drill-down (spec render-path table). Inputs are native widgets.
#
# Build phase: barebones. Structure, real data, correct render path. Styling
# (CSS polish, the segment cards as cards) is a later pass.

import streamlit as st

# Importing core runs core/__init__.py, which fixes sys.path so the plain
# imports below work under streamlit run and under a direct import.
import core  # noqa: F401
import config
import schema
from core import loader, clean, metrics
from components import html as H

WARNA = config.WARNA


def _section_title(text):
    """Section heading, one clear step below the page title (no accent tick).

    Same treatment as Monitoring, Matching, and Analitik so the four pages read
    as one product: navy, 1.12rem, no left accent bar.
    """
    st.markdown(
        "<div style='font-size:1.12rem;font-weight:700;color:" + WARNA["navy"]
        + ";margin:1.4rem 0 0.4rem;letter-spacing:-0.01em;'>" + H._esc(text)
        + "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Data. Loaded and cleaned once by the cached loader. Page config, global CSS,
# and the shared sidebar are set once by app.py (the st.navigation controller),
# not here. This page reads the date filter from session_state.
# ---------------------------------------------------------------------------

raw = loader.load_data()
data = clean.clean_data(raw)

ts = data.tracking_student
ss = data.status_student
sa = data.student_all
tc = data.tracking_company
co = data.company

# Date filter comes from the shared sidebar (set in app.py). Basis send_date:
# tc is filtered by send_date, then the tracking queue (ts) is restricted to
# the surviving tracking_company ids (same join pattern as Monitoring).
periode_filter = st.session_state.get("rentang_periode")
if periode_filter:
    start, end = periode_filter
    tc = tc[(tc["send_date"] >= start) & (tc["send_date"] <= end)]
    valid_tc_ids = set(tc["id_tracking_company"].dropna())
    ts = ts[ts["id_tracking_company"].isin(valid_tc_ids)]

st.markdown(
    H.page_header(
        "Beranda",
        "Antrean tindak lanjut. Paling mendesak di atas. Klik satu baris untuk melihat seluruh proses mahasiswa itu.",
    ),
    unsafe_allow_html=True,
)


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
                   "total 4 segmen tunggakan, tanpa Eligible", accent=WARNA["warn"]),
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

_section_title("Pilih segmen")

# Reverse map: a funnel stage (progress_student) to its Beranda segment. Built
# from BERANDA_SEGMEN_PROGRESS so the two never drift apart.
_STAGE_TO_SEGMEN = {
    stage: seg
    for seg, stages in schema.BERANDA_SEGMEN_PROGRESS.items()
    for stage in stages
}


def _normalize_beranda_segment(value):
    """Resolve session_state['beranda_segment'] to a valid segment name.

    A cross-link from Monitoring writes a dict {"stage": ..., "source_page":
    ...} (spec 6.1 point 6), not a segment name. Map that stage to its Beranda
    segment. A plain string that is already a valid segment passes through.
    Anything unmappable falls back to the most urgent segment, so the page
    never crashes on an unexpected value.
    """
    default = schema.BERANDA_SEGMEN_ORDER[0]
    if isinstance(value, dict):
        stage = value.get("stage")
        return _STAGE_TO_SEGMEN.get(stage, default)
    if value in schema.BERANDA_SEGMEN_ORDER:
        return value
    return default


# Default to the most urgent segment. A cross-link from Monitoring may have
# already written st.session_state['beranda_segment'] (spec 6.1 point 6), so
# normalize whatever is there to a valid segment name before using it.
st.session_state["beranda_segment"] = _normalize_beranda_segment(
    st.session_state.get("beranda_segment")
)


def _seg_button(seg):
    """Render one segment button. Active segment is primary styled."""
    selected = st.session_state["beranda_segment"] == seg
    label = seg + "  (" + H._fmt_id(seg_counts[seg]) + ")"
    if st.button(label, key="seg_btn_" + seg, use_container_width=True,
                 type="primary" if selected else "secondary"):
        st.session_state["beranda_segment"] = seg
        st.rerun()


# Four follow-up (backlog) segments first. Eligible is a different category, so
# it is separated below, not lined up as if it were a fifth backlog queue.
followup_segs = [
    s for s in schema.BERANDA_SEGMEN_ORDER if s != schema.SEG_ELIGIBLE
]
seg_cols = st.columns(len(followup_segs))
for i, seg in enumerate(followup_segs):
    with seg_cols[i]:
        _seg_button(seg)

# Eligible segment: opportunity, not backlog. Visually set apart with its own
# row and a one-line note so the "4 segmen aktif" KPI does not look off by one.
st.caption(
    "Segmen berikut  menunjukkan peluang mahasiswa siap menjadi kandidat tetapi belum dikirimkan. Tidak termasuk dalam total 4 segmen aktif di kartu atas."
)
elig_col, _elig_spacer = st.columns([1, 3])
with elig_col:
    _seg_button(schema.SEG_ELIGIBLE)

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
        # NIM in its own column, not glued into the name, so the name column is
        # not stretched wide by a parenthesized number (frees room for Kontak).
        disp["Kontak"] = disp["hp"].map(H.wa_url)
        view = disp[[
            "nama", "NIM", "program_studi", "IPK", "domisili", "CV", "Kontak",
        ]].rename(columns={
            "nama": "Nama", "program_studi": "Program", "domisili": "Domisili",
        })
        return disp, view, True

    q = metrics.beranda_queue(ts, data.ANCHOR)
    q = q[q["segmen"] == active_seg].copy()
    q = q.merge(sa[["NIM", "hp"]], on="NIM", how="left").reset_index(drop=True)
    q["Perusahaan & posisi"] = q["company"] + " - " + q["position"]
    q["Kontak"] = q["hp"].map(H.wa_url)
    view = q[[
        "student_name", "NIM", "Perusahaan & posisi", "progress_student",
        "diam_hari", "Kontak",
    ]].rename(columns={
        "student_name": "Nama", "progress_student": "Tahap",
        "diam_hari": "Diam (hari)",
    })
    return q, view, False


disp_full, view, is_eligible = _build_queue_display(active_seg)

# Search filter over NIM, name, and company (native input, placeholder inside).
cari = st.text_input(
    "Cari NIM, nama, atau perusahaan",
    key="cari_queue",
    placeholder="Ketik NIM, nama, atau perusahaan",
)
if cari.strip():
    key = cari.strip().lower()
    hay = disp_full["NIM"].astype(str).str.lower()
    name_col = "nama" if is_eligible else "student_name"
    hay = hay + " " + disp_full[name_col].astype(str).str.lower()
    if not is_eligible:
        hay = hay + " " + disp_full["Perusahaan & posisi"].str.lower()
    keep = hay.str.contains(key, na=False)
    disp_full = disp_full[keep].reset_index(drop=True)
    view = view.loc[disp_full.index].reset_index(drop=True)


# Read any prior selection first: the layout depends on whether a row is
# already selected. At rest (no selection) the queue table takes the full width
# so every column, including Kontak, is readable. Once a row is picked the
# detail panel opens beside a narrower table.
def _selected_rows(state):
    """Pull the selected row indices out of a dataframe widget state.

    The st.dataframe selection state can be an object with a .selection
    attribute or a plain dict, depending on context. Handle both, and always
    return a list of row indices.
    """
    if state is None:
        return []
    selection = getattr(state, "selection", None)
    if selection is None and isinstance(state, dict):
        selection = state.get("selection")
    if selection is None:
        return []
    rows = getattr(selection, "rows", None)
    if rows is None and isinstance(selection, dict):
        rows = selection.get("rows")
    return list(rows) if rows else []


prev_rows = _selected_rows(st.session_state.get("queue_df"))
has_selection = bool(prev_rows) and prev_rows[0] < len(view)


def _render_queue():
    """Render the queue header and selectable table. Returns the select event."""
    _section_title(active_seg + "  (" + H._fmt_id(len(view)) + " baris)")
    if not is_eligible:
        st.caption(
            "Kolom Diam (hari) dihitung terhadap tanggal acuan "
        )
    link_col = st.column_config.LinkColumn("Kontak", display_text="WhatsApp")
    return st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Kontak": link_col,
            "NIM": st.column_config.TextColumn("NIM", width="small"),
        },
        height=420,
        key="queue_df",
    )


if not has_selection:
    # Full-width table at rest. The detail panel prompt sits below, compact.
    event = _render_queue()
    sel_rows = _selected_rows(event)
    if not sel_rows:
        st.caption("Klik satu baris di antrean untuk melihat profil dan semua "
                   "prosesnya di panel detail.")

if has_selection:
    left, right = st.columns([3, 2])
    with left:
        event = _render_queue()
    right_ctx = right
else:
    right_ctx = None


# ---------------------------------------------------------------------------
# Drill-down panel. The team differentiator: one student, every process.
# Only rendered once a row is selected, beside a narrower table.
# ---------------------------------------------------------------------------

sel_rows = _selected_rows(event)

if sel_rows and right_ctx is not None:
    with right_ctx:
        _section_title("Detail mahasiswa")
        idx = sel_rows[0]
        nim = str(disp_full.iloc[idx]["NIM"])

        prof_rows = ss[ss["NIM"] == nim]
        if len(prof_rows) == 0:
            st.warning("Profil status_student tidak ditemukan untuk NIM ini.")
        else:
            prof = prof_rows.iloc[0]

            # Identity first, plain text (not a callout box) - so the first
            # thing read is unmistakably "this is who", before any status or
            # warning competes for attention.
            tools = prof.get("tools_list") or []
            tools_txt = ", ".join(tools) if len(tools) else "tidak tercatat"
            ipk_txt = "-" if prof["IPK"] is None else str(prof["IPK"])

            st.markdown("##### " + prof["nama"] + " (" + nim + ")")
            st.caption(
                "Program: " + str(prof["program_studi"])
                + ", IPK: " + ipk_txt
                + ", Domisili: " + str(prof["domisili"])
            )
            st.caption("Tools: " + tools_txt)

            # CV status right under identity.
            cv_badge = H.badge(
                "CV ada" if prof["CV"] == schema.CV_ADA else "tanpa CV",
                "ok" if prof["CV"] == schema.CV_ADA else "warn",
            )
            st.markdown(cv_badge, unsafe_allow_html=True)

            # Placed-elsewhere warning comes after identity/CV: it is an
            # alert about this student, not part of who they are.
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
