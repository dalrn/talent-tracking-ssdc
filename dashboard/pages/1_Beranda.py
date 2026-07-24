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
from components import styles as S

WARNA = config.WARNA


# ---------------------------------------------------------------------------
# Data. Loaded and cleaned once by the cached loader.
# ---------------------------------------------------------------------------

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
