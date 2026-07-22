# pages/3_Monitoring.py
# Owner: Afrizal. Monitoring funnel and ghosting (BT-02, BT-05, part BT-04).
# See spec Section 6.3. Question this page answers: "Di mana pipeline bocor,
# dan pola apa yang sistemik."
#
# Rules followed (kept consistent with pages/4_Analitik.py):
# - No metric is recomputed here. Every number comes from core/metrics.py.
# - No CSV is read here. Data comes from core/loader + core/clean.
# - Category values come from core/schema.py, never raw strings.
# - Colors come from config.WARNA, no hex is written in this file.
# - Charts use Plotly. Cards, badges, callouts, tables use HTML helpers from
#   components/html.py. Inputs use native Streamlit widgets.
# - Drill-down tables use native Streamlit buttons / st.switch_page.

import plotly.graph_objects as go
import streamlit as st

# Importing the core package runs core/__init__.py, which puts dashboard/ and
# dashboard/core/ on sys.path. That makes the plain imports below work whether
# this page is launched by streamlit run or imported directly.
import core  # noqa: F401
import config
import schema
from core import loader, clean, metrics
from components import html as H

WARNA = config.WARNA


# ---------------------------------------------------------------------------
# Data. Loaded and cleaned once by the cached loader.
# ---------------------------------------------------------------------------

raw = loader.load_data()
data = clean.clean_data(raw)

tracking_student = data.tracking_student
tracking_company = data.tracking_company
ANCHOR = data.ANCHOR

st.set_page_config(page_title="Monitoring SSDC", layout="wide")
st.title("Monitoring")
st.caption("Di mana pipeline bocor, dan pola apa yang sistemik. Data per "
           + str(ANCHOR.date()) + ".")


# ---------------------------------------------------------------------------
# Global filters from st.session_state (set elsewhere, likely app.py).
# This page reads them if present. It does NOT create the filter widgets.
# Basis for the period filter on this page: send_date (per project note).
# ---------------------------------------------------------------------------

jenis_penempatan_filter = st.session_state.get("jenis_penempatan", "Semua")
prodi_filter = st.session_state.get("prodi", "Semua")
periode_filter = st.session_state.get("rentang_periode", None)  # (start, end) or None

ts_filtered = tracking_student
tc_filtered = tracking_company

if jenis_penempatan_filter and jenis_penempatan_filter != "Semua":
    ts_filtered = ts_filtered[ts_filtered["jenis_penempatan"] == jenis_penempatan_filter]
    tc_filtered = tc_filtered[tc_filtered["jenis_penempatan"] == jenis_penempatan_filter]

if prodi_filter and prodi_filter != "Semua":
    # TODO(Afrizal): confirm whether global prodi filter targets tracking_student
    # directly (no prodi column here natively - it lives on student_all/status_student)
    # or whether it should join through NIM. Placeholder: skip until confirmed,
    # so the page does not silently drop rows on a column that may not exist here.
    pass

if periode_filter:
    start, end = periode_filter
    tc_filtered = tc_filtered[
        (tc_filtered["send_date"] >= start) & (tc_filtered["send_date"] <= end)
    ]
    # ts_filtered has no send_date of its own; it is joined to tracking_company
    # via id_tracking_company. Restrict ts_filtered to tracking rows whose
    # parent tracking_company passed the period filter.
    valid_tc_ids = set(tc_filtered["id_tracking_company"].dropna())
    ts_filtered = ts_filtered[ts_filtered["id_tracking_company"].isin(valid_tc_ids)]


tab_mahasiswa, tab_perusahaan = st.tabs(["Mahasiswa", "Perusahaan"])

# =============================================================================
# TAB 1 — MAHASISWA
# =============================================================================
with tab_mahasiswa:

    # =======================================================================
    # 1. Funnel seleksi (BT-02).
    # =======================================================================
    st.markdown("## 1. Funnel seleksi")
    st.caption("Posisi setiap proses aktif di funnel, dan di mana kandidat "
               "berguguran.")

    active_counts = metrics.funnel_active_counts(ts_filtered)
    drop_counts = metrics.funnel_drop_counts(ts_filtered)

    stages = schema.FUNNEL_ORDER  # top to bottom order, per schema.py
    active_vals = [active_counts[s] for s in stages]
    # drop_counts has no entry for CDC Briefing (REJ_GATE_MAP has none), 0 fallback.
    drop_vals = [drop_counts.get(s, 0) for s in stages]

    fig = go.Figure(
        go.Funnel(
            y=stages,
            x=active_vals,
            textinfo="value+percent initial",
            marker=dict(color=WARNA["bar"]),
            connector=dict(line=dict(color=WARNA["line"])),
        )
    )
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Automatic callout: biggest bottleneck, computed not hardcoded.
    if any(v > 0 for v in drop_vals):
        bottleneck_stage = max(drop_counts, key=drop_counts.get)
        bottleneck_val = drop_counts[bottleneck_stage]
        st.markdown(
            H.callout(
                str(bottleneck_val) + " kandidat gugur di tahap ini, kebocoran "
                "terbesar di sepanjang funnel.",
                kind="watch", title="Kebocoran terbesar: " + str(bottleneck_stage),
            ),
            unsafe_allow_html=True,
        )

    # =======================================================================
    # 2. Tahapan funnel. Klik untuk buka daftar di Beranda.
    # =======================================================================
    st.markdown("## 2. Tahapan")
    st.caption("Klik Buka untuk membuka daftar kandidat tahap itu di Beranda.")

    for stage in stages:
        col_label, col_btn = st.columns([5, 1])
        with col_label:
            gugur = drop_counts.get(stage, 0)
            if stage in drop_counts:
                sub = str(active_counts[stage]) + " aktif, " + str(gugur) + " gugur"
            else:
                sub = str(active_counts[stage]) + " aktif, tidak ada gerbang gugur"
            st.markdown(
                H.kpi_card(stage, str(active_counts[stage]) + " aktif", sub,
                           accent=WARNA["ink"]),
                unsafe_allow_html=True,
            )
        with col_btn:
            # Native button required to catch a click (Plotly funnel click-event
            # is not reliably capturable), per spec point 2c.
            if st.button("Buka", key="buka_" + stage):
                st.session_state["beranda_segment"] = {
                    "stage": stage,
                    "source_page": "Monitoring",
                }
                st.switch_page("pages/1_Beranda.py")

    # =======================================================================
    # 3. Performa perusahaan (ringkas). Analisis penuh ada di Analitik.
    # =======================================================================
    st.markdown("## 3. Performa perusahaan (ringkas)")
    st.caption("Versi operasional ringkas. Analisis penuh ada di halaman "
               "Analitik.")

    league = metrics.company_league(ts_filtered, min_n=config.MIN_N_RANKING)
    top5 = league.sort_values("rate", ascending=False).head(5)
    bottom5 = league.sort_values("rate", ascending=True).head(5)

    def _league_table(df):
        columns = ["Perusahaan", "Kirim", "Placement", "Rate"]
        align = ["left", "right", "right", "right"]
        rows = []
        for _, r in df.iterrows():
            perusahaan = H._esc(r["company"])
            if not r["lolos_gate"]:
                perusahaan = perusahaan + " " + H.badge("n kecil", "warn")
            rows.append([
                perusahaan,
                int(r["n"]),
                int(r["k"]),
                str(round(r["rate"] * 100, 1)) + "%",
            ])
        return H.read_only_table(columns, rows, align=align, raw_html_cols={0})

    col_top, col_bottom = st.columns(2)
    with col_top:
        st.markdown("### Tertinggi")
        st.markdown(_league_table(top5), unsafe_allow_html=True)
    with col_bottom:
        st.markdown("### Terendah")
        st.markdown(_league_table(bottom5), unsafe_allow_html=True)

# =============================================================================
# TAB 2 — PERUSAHAAN (owner-decided: Afrizal, kerangka disiapkan)
# =============================================================================
with tab_perusahaan:

    # =======================================================================
    # 1. Pola ghosting. Dua angka: pelaporan vs operasional.
    # =======================================================================
    st.markdown("## 1. Pola ghosting")
    st.caption("Tingkat sistem, bukan per orang.")

    n_reporting = int(metrics.ghosting_reporting_mask(ts_filtered).sum())
    n_operasional = int(metrics.ghosting_operasional_mask(ts_filtered).sum())

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            H.kpi_card(
                "Total pelaporan (rejection == Ghosting)",
                str(n_reporting),
                "Semua kasus yang pernah berstatus Ghosting sepanjang riwayat",
                accent=WARNA["accent"], big=True,
            ),
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            H.kpi_card(
                "Aktif operasional (progress_student == Ghosting)",
                str(n_operasional),
                "Hanya proses yang saat ini masih berstatus Ghosting",
                accent=WARNA["accent"], big=True,
            ),
            unsafe_allow_html=True,
        )
    st.markdown(
        H.callout(
            "Angka pelaporan mencakup semua kasus yang pernah berstatus "
            "Ghosting sepanjang riwayat, termasuk yang sudah diarsipkan ke "
            "Finish. Angka operasional hanya proses yang saat ini masih "
            "berstatus Ghosting dan belum ditindaklanjuti.",
            kind="accent", title="Kenapa dua angka ini berbeda",
        ),
        unsafe_allow_html=True,
    )

    # =======================================================================
    # 2. Klasifikasi tipe ghosting.
    # =======================================================================
    st.markdown("## 2. Klasifikasi tipe ghosting")

    klas = metrics.klasifikasi_ghosting(
        ts_filtered, ghosting_mask=metrics.ghosting_reporting_mask(ts_filtered)
    )
    tipe_counts = klas["tipe_ghosting"].value_counts()

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(
            H.kpi_card("Kemungkinan murni perusahaan",
                       str(int(tipe_counts.get("murni_perusahaan", 0))),
                       accent=WARNA["ink"]),
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            H.kpi_card("Kemungkinan mahasiswa mangkir",
                       str(int(tipe_counts.get("mahasiswa_mangkir", 0))),
                       accent=WARNA["ink"]),
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            H.kpi_card("Tak tentu",
                       str(int(tipe_counts.get("tak_tentu", 0))),
                       accent=WARNA["ink"]),
            unsafe_allow_html=True,
        )
    st.markdown(
        H.callout(
            "Label 'kemungkinan' dipakai karena klasifikasi ini inferensi dari "
            "urutan tanggal last_update terhadap tanggal placement, bukan "
            "keterangan eksplisit di data tentang siapa yang tidak merespons.",
            kind="muted",
        ),
        unsafe_allow_html=True,
    )

    # =======================================================================
    # 3. Rate ghosting tertinggi. Dua versi berdampingan.
    # =======================================================================
    st.markdown("## 3. Rate ghosting tertinggi (n >= " + str(config.MIN_N_RANKING)
                + ")")

    ghost_all = metrics.ghosting_rate_per_company(ts_filtered, min_n=config.MIN_N_RANKING)
    ghost_murni = metrics.ghosting_rate_per_company_murni(ts_filtered, min_n=config.MIN_N_RANKING)

    def _ghost_table(df):
        gated = df[df["lolos_gate"]].sort_values("rate", ascending=False).head(5)
        columns = ["Perusahaan", "Kirim", "Ghosting", "Rate"]
        align = ["left", "right", "right", "right"]
        rows = []
        for _, r in gated.iterrows():
            rows.append([
                r["company"],
                int(r["n"]),
                int(r["k"]),
                str(round(r["rate"] * 100, 1)) + "%",
            ])
        return H.read_only_table(columns, rows, align=align)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### Semua ghosting")
        st.markdown(_ghost_table(ghost_all), unsafe_allow_html=True)
    with col_b:
        st.markdown("### Murni perusahaan saja")
        st.markdown(_ghost_table(ghost_murni), unsafe_allow_html=True)

    worst_company, worst_k = metrics.max_ghosting_case_company(
        ts_filtered, min_n=config.MIN_N_RANKING
    )
    if worst_company is not None:
        st.markdown(
            H.callout(
                "Perusahaan ghosting terbanyak pun hanya " + str(worst_k)
                + " kasus (" + str(worst_company) + "). Artinya ghosting adalah "
                "masalah sistemik yang butuh mekanisme follow up terstruktur, "
                "bukan sekadar menandai beberapa perusahaan.",
                kind="watch", title="Tersebar, bukan segelintir pelaku",
            ),
            unsafe_allow_html=True,
        )

    # TODO(Afrizal): confirm whether the two leaderboards should be side by
    # side (current layout) or toggled via a single selectbox/radio, per
    # spec point 3d ("berdampingan atau lewat toggle" - left open to owner).

    # =======================================================================
    # 4. Status request per perusahaan (BT-05). Draft + response time.
    # =======================================================================
    st.markdown("## 4. Status request per perusahaan")

    draft_df = metrics.draft_requests(tc_filtered)
    st.markdown(
        H.kpi_card(
            "Request berstatus Draft (belum dilayani)",
            str(len(draft_df)),
            "Relatif terhadap tanggal acuan " + str(ANCHOR.date()),
            accent=WARNA["ink"],
        ),
        unsafe_allow_html=True,
    )

    # TODO(Afrizal): decide which age metric fits best here - request_age_days()
    # (age since request_date, frames "how long has this waited") vs idle_days()
    # (age since last_update on tracking_student, frames "how long since last
    # movement"). Draft rows have no tracking_student child yet, so
    # request_age_days() is used below as the working default - confirm this
    # is the intended framing before final submission.
    if not draft_df.empty:
        draft_display = draft_df.copy()
        draft_display["usia_hari"] = metrics.request_age_days(draft_display, ANCHOR)

        columns = ["Perusahaan", "Usia request"]
        align = ["left", "right"]
        rows = []
        for _, r in draft_display.sort_values("usia_hari", ascending=False).head(10).iterrows():
            rows.append([
                r.get("nama_perusahaan", ""),
                str(int(r["usia_hari"])) + " hari",
            ])
        st.markdown(
            H.read_only_table(columns, rows, align=align),
            unsafe_allow_html=True,
        )

# =============================================================================
# Definition footer. Keep Monitoring and Analitik consistent for judges.
# =============================================================================

n_stage_placement = int(metrics.is_stage_placement(ts_filtered).sum())
n_success_placement = int(metrics.is_placement_success(ts_filtered).sum())
selisih = n_success_placement - n_stage_placement

st.markdown("---")
st.markdown(
    H.callout(
        "Funnel di halaman ini memakai kolom progress_student untuk posisi "
        "aktif, totalnya " + str(n_stage_placement) + " di tahap Placement. "
        "Definisi resmi keberhasilan (BT-04) memakai kolom rejection == "
        "Placement, totalnya " + str(n_success_placement) + ". Selisih "
        + str(selisih) + " adalah placement yang sudah diarsipkan ke Finish, "
        "tetap dihitung berhasil. Kolom tracking_company.progress tidak dipakai "
        "di halaman ini kecuali untuk mendeteksi status Draft pada request. Ini "
        "konsisten dengan halaman Analitik.",
        kind="muted", title="Catatan definisi",
    ),
    unsafe_allow_html=True,
)
