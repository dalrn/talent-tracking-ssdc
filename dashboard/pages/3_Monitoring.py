# pages/3_Monitoring.py
# Owner: Afrizal. Purpose: Monitoring funnel and ghosting (BT-02, BT-05, part BT-04). See spec Section 6.3.

# pages/3_Monitoring.py
# Monitoring page (owner: Afrizal). BT-02 and BT-05 at pipeline level,
# partial BT-04. Question this page answers: "Di mana pipeline bocor, dan
# pola apa yang sistemik."
#
# Render rules (Section 5, project spec):
# - KPI cards, badges, headers, callouts, read-only tables -> plain HTML via
#   st.markdown(unsafe_allow_html=True). No CSS/color yet, components/styles.py
#   is still empty.
# - Charts -> Plotly only.
# - Inputs (toggle/slider/selectbox) -> native Streamlit.
# - Drill-down tables -> st.dataframe(on_select="rerun", selection_mode=...).
# All formulas live in core/metrics.py. This file only calls them.

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import schema
from core import metrics
from core.clean import clean_data
from core.loader import load_data

st.set_page_config(page_title="Monitoring - TalentTrack", layout="wide")

# ---------------------------------------------------------------------------
# Load and clean data, following the RawData -> CleanData pattern.
# ---------------------------------------------------------------------------
raw = load_data()
clean = clean_data(raw)

tracking_student = clean.tracking_student
tracking_company = clean.tracking_company
ANCHOR = clean.ANCHOR

# ---------------------------------------------------------------------------
# Apply GLOBAL filters from st.session_state (set elsewhere, likely app.py).
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

# ---------------------------------------------------------------------------
# Header (HTML, no CSS yet)
# ---------------------------------------------------------------------------
st.markdown(
    "<h1>Monitoring</h1>"
    "<p>Di mana pipeline bocor, dan pola apa yang sistemik.</p>",
    unsafe_allow_html=True,
)

tab_mahasiswa, tab_perusahaan = st.tabs(["Mahasiswa", "Perusahaan"])

# =============================================================================
# TAB 1 — MAHASISWA
# =============================================================================
with tab_mahasiswa:

    st.markdown(
        "<h2>Funnel Seleksi</h2>"
        "<p>Posisi setiap proses aktif di funnel, dan di mana kandidat berguguran.</p>",
        unsafe_allow_html=True,
    )

    # --- data for the funnel, from metrics.py only ---
    active_counts = metrics.funnel_active_counts(ts_filtered)
    drop_counts = metrics.funnel_drop_counts(ts_filtered)

    stages = schema.FUNNEL_ORDER  # top to bottom order, per schema.py
    active_vals = [active_counts[s] for s in stages]
    # drop_counts has no entry for CDC Briefing (REJ_GATE_MAP has none), 0 fallback.
    drop_vals = [drop_counts.get(s, 0) for s in stages]

    # --- Plotly go.Funnel, horizontal (native orientation of go.Funnel) ---
    fig = go.Figure(
        go.Funnel(
            y=stages,
            x=active_vals,
            textinfo="value+percent initial",
        )
    )
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # --- automatic HTML callout: biggest bottleneck, computed not hardcoded ---
    if any(v > 0 for v in drop_vals):
        bottleneck_stage = max(drop_counts, key=drop_counts.get)
        bottleneck_val = drop_counts[bottleneck_stage]
        st.markdown(
            f"<div><strong>Kebocoran terbesar: {html.escape(bottleneck_stage)}</strong> "
            f"({bottleneck_val:,} gugur).</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<hr/>", unsafe_allow_html=True)

    # --- per-stage rows: HTML label + small native button to drill into Beranda ---
    st.markdown("<h3>Tahapan (klik untuk buka daftar di Beranda)</h3>", unsafe_allow_html=True)
    for stage in stages:
        col_label, col_btn = st.columns([5, 1])
        with col_label:
            gugur = drop_counts.get(stage, 0)
            gugur_text = f"{gugur:,} gugur" if stage in drop_counts else "tidak ada gerbang gugur"
            st.markdown(
                f"<div><strong>{html.escape(stage)}</strong> — "
                f"{active_counts[stage]:,} aktif, {gugur_text}</div>",
                unsafe_allow_html=True,
            )
        with col_btn:
            # Native button required to catch a click (Plotly funnel click-event
            # is not reliably capturable), per spec point 2c.
            if st.button("Buka →", key=f"buka_{stage}"):
                st.session_state["beranda_segment"] = {
                    "stage": stage,
                    "source_page": "Monitoring",
                }
                st.switch_page("pages/1_Beranda.py")

    st.markdown("<hr/>", unsafe_allow_html=True)

    # --- ringkasan performa perusahaan (read-only HTML table, top & bottom) ---
    st.markdown(
        "<h2>Performa Perusahaan (Ringkas)</h2>"
        "<p>Versi operasional ringkas. Analisis penuh ada di halaman Analitik.</p>",
        unsafe_allow_html=True,
    )

    league = metrics.company_league(ts_filtered, min_n=config.MIN_N_RANKING)
    top5 = league.sort_values("rate", ascending=False).head(5)
    bottom5 = league.sort_values("rate", ascending=True).head(5)

    def _render_league_table_html(df, judul):
        rows_html = ""
        for _, row in df.iterrows():
            badge = (
                "<span> [n kecil]</span>" if not row["lolos_gate"] else ""
            )
            rate_pct = round(row["rate"] * 100, 1)
            rows_html += (
                f"<tr>"
                f"<td>{html.escape(str(row['company']))}{badge}</td>"
                f"<td>{int(row['n'])}</td>"
                f"<td>{int(row['k'])}</td>"
                f"<td>{rate_pct}%</td>"
                f"</tr>"
            )
        return (
            f"<h3>{judul}</h3>"
            "<table>"
            "<thead><tr><th>Perusahaan</th><th>Kirim</th><th>Placement</th><th>Rate</th></tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            "</table>"
        )

    col_top, col_bottom = st.columns(2)
    with col_top:
        st.markdown(_render_league_table_html(top5, "Tertinggi"), unsafe_allow_html=True)
    with col_bottom:
        st.markdown(_render_league_table_html(bottom5, "Terendah"), unsafe_allow_html=True)

# =============================================================================
# TAB 2 — PERUSAHAAN (owner-decided: Afrizal, kerangka disiapkan)
# =============================================================================
with tab_perusahaan:

    st.markdown("<h2>Pola Ghosting</h2><p>Tingkat sistem, bukan per orang.</p>", unsafe_allow_html=True)

    # --- 3a: dua angka ghosting, reporting vs operasional ---
    n_reporting = int(metrics.ghosting_reporting_mask(ts_filtered).sum())
    n_operasional = int(metrics.ghosting_operasional_mask(ts_filtered).sum())

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"<div><strong>{n_reporting:,}</strong><br/>"
            f"Total pelaporan (rejection == Ghosting)</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"<div><strong>{n_operasional:,}</strong><br/>"
            f"Aktif operasional saat ini (progress_student == Ghosting)</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<p>Angka pelaporan mencakup semua kasus yang pernah berstatus "
        "Ghosting sepanjang riwayat, termasuk yang sudah diarsipkan ke "
        "Finish. Angka operasional hanya proses yang SAAT INI masih "
        "berstatus Ghosting dan belum ditindaklanjuti.</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<hr/>", unsafe_allow_html=True)

    # --- 3b: klasifikasi 3 tipe ghosting ---
    st.markdown("<h3>Klasifikasi Tipe Ghosting</h3>", unsafe_allow_html=True)
    klas = metrics.klasifikasi_ghosting(
        ts_filtered, ghosting_mask=metrics.ghosting_reporting_mask(ts_filtered)
    )
    tipe_counts = klas["tipe_ghosting"].value_counts()

    st.markdown(
        f"<div>Kemungkinan murni perusahaan: <strong>{int(tipe_counts.get('murni_perusahaan', 0)):,}</strong></div>"
        f"<div>Kemungkinan mahasiswa mangkir: <strong>{int(tipe_counts.get('mahasiswa_mangkir', 0)):,}</strong></div>"
        f"<div>Tak tentu: <strong>{int(tipe_counts.get('tak_tentu', 0)):,}</strong></div>"
        "<p>Label 'kemungkinan' dipakai karena klasifikasi ini inferensi dari "
        "urutan tanggal last_update terhadap tanggal placement, bukan "
        "keterangan eksplisit di data tentang siapa yang tidak merespons.</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<hr/>", unsafe_allow_html=True)

    # --- 3c/3d: leaderboard rate ghosting, dua versi berdampingan ---
    st.markdown(
        f"<h3>Rate Ghosting Tertinggi (N ≥ {config.MIN_N_RANKING})</h3>",
        unsafe_allow_html=True,
    )

    ghost_all = metrics.ghosting_rate_per_company(ts_filtered, min_n=config.MIN_N_RANKING)
    ghost_murni = metrics.ghosting_rate_per_company_murni(ts_filtered, min_n=config.MIN_N_RANKING)

    def _render_ghost_table_html(df, judul):
        gated = df[df["lolos_gate"]].sort_values("rate", ascending=False).head(5)
        rows_html = ""
        for _, row in gated.iterrows():
            rate_pct = round(row["rate"] * 100, 1)
            rows_html += (
                f"<tr><td>{html.escape(str(row['company']))}</td>"
                f"<td>{int(row['n'])}</td><td>{int(row['k'])}</td>"
                f"<td>{rate_pct}%</td></tr>"
            )
        return (
            f"<h4>{judul}</h4>"
            "<table><thead><tr><th>Perusahaan</th><th>Kirim</th><th>Ghosting</th><th>Rate</th></tr></thead>"
            f"<tbody>{rows_html}</tbody></table>"
        )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(_render_ghost_table_html(ghost_all, "Semua Ghosting"), unsafe_allow_html=True)
    with col_b:
        st.markdown(
            _render_ghost_table_html(ghost_murni, "Murni Perusahaan Saja"),
            unsafe_allow_html=True,
        )

    worst_company, worst_k = metrics.max_ghosting_case_company(
        ts_filtered, min_n=config.MIN_N_RANKING
    )
    if worst_company is not None:
        st.markdown(
            f"<p><strong>Tersebar, bukan segelintir pelaku.</strong> Perusahaan "
            f"ghosting terbanyak pun hanya <strong>{worst_k:,} kasus</strong> "
            f"({html.escape(str(worst_company))}). Artinya ghosting adalah masalah "
            f"sistemik yang butuh mekanisme follow up terstruktur, bukan sekadar "
            f"menandai beberapa perusahaan.</p>",
            unsafe_allow_html=True,
        )

    # TODO(Afrizal): confirm whether the two leaderboards should be side by
    # side (current layout) or toggled via a single selectbox/radio, per
    # spec point 3d ("berdampingan atau lewat toggle" - left open to owner).

    st.markdown("<hr/>", unsafe_allow_html=True)

    # --- 3e: status request per perusahaan (draft + response time) ---
    st.markdown("<h3>Status Request per Perusahaan</h3>", unsafe_allow_html=True)

    draft_df = metrics.draft_requests(tc_filtered)
    st.markdown(
        f"<div><strong>{len(draft_df):,}</strong> request berstatus Draft "
        f"(belum dilayani).</div>",
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

        rows_html = ""
        for _, row in draft_display.sort_values("usia_hari", ascending=False).head(10).iterrows():
            rows_html += (
                f"<tr><td>{html.escape(str(row.get('nama_perusahaan', '')))}</td>"
                f"<td>{int(row['usia_hari'])} hari</td></tr>"
            )
        st.markdown(
            "<table><thead><tr><th>Perusahaan</th><th>Usia Request</th></tr></thead>"
            f"<tbody>{rows_html}</tbody></table>",
            unsafe_allow_html=True,
        )

# =============================================================================
# FOOTER (HTML, below both tabs)
# =============================================================================
n_stage_placement = int(metrics.is_stage_placement(ts_filtered).sum())
n_success_placement = int(metrics.is_placement_success(ts_filtered).sum())

st.markdown("<hr/>", unsafe_allow_html=True)
st.markdown(
    f"<p><strong>Catatan angka placement.</strong> Halaman ini menampilkan dua "
    f"kemungkinan angka placement yang berbeda secara sengaja, bukan salah hitung:</p>"
    f"<ul>"
    f"<li><strong>{n_stage_placement:,}</strong> — proses yang tahap terkininya "
    f"(<code>progress_student == {schema.STAGE_PLACEMENT}</code>) adalah Placement. "
    f"Ini yang dipakai funnel di halaman ini untuk posisi aktif tiap proses.</li>"
    f"<li><strong>{n_success_placement:,}</strong> — proses yang status akhirnya "
    f"(<code>rejection == {schema.REJ_PLACEMENT}</code>) adalah Placement. Ini "
    f"definisi resmi keberhasilan (BT-04) yang dipakai success rate di halaman lain.</li>"
    f"</ul>"
    f"<p>Funnel di halaman ini memakai <code>progress_student</code> untuk hitung "
    f"aktif, dan <code>rejection</code> untuk hitung gugur di tiap gerbang. Kolom "
    f"<code>tracking_company.progress</code> TIDAK dipakai sama sekali di halaman "
    f"ini, kecuali untuk menghitung status Draft pada request (tab Perusahaan) — "
    f"kolom itu tidak sinkron pada level detail, sesuai temuan cleaning data.</p>",
    unsafe_allow_html=True,
)