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

import streamlit as st

# Importing the core package runs core/__init__.py, which puts dashboard/ and
# dashboard/core/ on sys.path. That makes the plain imports below work whether
# this page is launched by streamlit run or imported directly.
import core  # noqa: F401
import config
import schema
from core import loader, clean, metrics
import components.html as H
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
    # 1. Funnel seleksi (BT-02). Active count + drop count per gate, absolute
    # numbers only. No Plotly go.Funnel / percent_initial: stage counts are
    # not monotonic (Interview User 3.278 > Selecting 1.673), which makes a
    # percent-of-initial reading misleading. Custom HTML bars via
    # H.funnel_bar() instead, all stages sharing one width scale.
    # =======================================================================
    st.markdown("## Funnel Seleksi")
    st.caption("Posisi setiap proses aktif di funnel, dan di mana kandidat "
               "berguguran. Klik satu tahap untuk buka daftarnya di Beranda.")

    active_counts = metrics.funnel_active_counts(ts_filtered)
    drop_counts = metrics.funnel_drop_counts(ts_filtered)

    stages = schema.FUNNEL_ORDER  # top to bottom order, per schema.py
    # drop_counts has no entry for CDC Briefing (REJ_GATE_MAP has none), 0 fallback.
    drop_vals = [drop_counts.get(s, 0) for s in stages]
    max_val = max(active_counts[s] + drop_counts.get(s, 0) for s in stages)

    STAGE_SUBLABELS = {
        schema.STAGE_SELECTING: "perusahaan meninjau profil",
        schema.STAGE_BRIEFING: "briefing oleh CDC",
        schema.STAGE_STUDYCASE: "tes / studi kasus",
        schema.STAGE_INTERVIEW: "wawancara hiring manager",
        schema.STAGE_FINAL: "wawancara tahap akhir",
        schema.STAGE_PLACEMENT: "diterima & ditempatkan",
    }
    STAGE_GUGUR_LABELS = {
        schema.STAGE_SELECTING: "gugur screening CV",
        schema.STAGE_STUDYCASE: "gugur study case",
        schema.STAGE_INTERVIEW: "gugur interview user",
        schema.STAGE_FINAL: "gugur final",
    }

    for stage in stages:
        col_bar, col_btn = st.columns([6, 1])
        with col_bar:
            st.markdown(
                H.funnel_bar(
                    label=stage,
                    sublabel=STAGE_SUBLABELS.get(stage, ""),
                    aktif=active_counts[stage],
                    gugur=drop_counts.get(stage, 0),
                    gugur_label=STAGE_GUGUR_LABELS.get(stage, ""),
                    accent=WARNA["bar"],
                    is_placement=(stage == schema.STAGE_PLACEMENT),
                    max_val=max_val,
                ),
                unsafe_allow_html=True,
            )
        with col_btn:
            # Native button required to catch a click (Plotly funnel click-event
            # is not reliably capturable), per spec point 2c.
            if st.button("Buka →", key="buka_" + stage):
                st.session_state["beranda_segment"] = {
                    "stage": stage,
                    "source_page": "Monitoring",
                }
                st.switch_page("pages/1_Beranda.py")

    st.markdown(
        '<div style="display:flex;gap:24px;align-items:center;'
        'margin-top:6px;font-size:0.8rem;color:' + WARNA["ink2"] + ';">'
        '<div><span style="display:inline-block;width:12px;height:12px;'
        'background:' + WARNA["bar"] + ';border-radius:2px;margin-right:6px;">'
        '</span>Aktif di tahap (progress_student)</div>'
        '<div><span style="display:inline-block;width:12px;height:12px;'
        'background:' + WARNA["ref"] + ';border-radius:2px;margin-right:6px;">'
        '</span>Gugur di tahap ini (rejection)</div>'
        '<div><span style="display:inline-block;width:12px;height:12px;'
        'background:' + WARNA["ok"] + ';border-radius:2px;margin-right:6px;">'
        '</span>Placement</div>'
        '</div>',
        unsafe_allow_html=True,
    )

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
    # 2. Performa perusahaan (ringkas). Analisis penuh ada di Analitik.
    # Single scrollable, sortable list (Wilson CI per company) replaces the
    # old top5/bottom5 side-by-side tables. league = metrics.company_league()
    # is the only source of n/k/rate/wilson_*; jenis_penempatan and
    # industry_sector below are descriptive lookups only, not metrics.
    # =======================================================================
    st.markdown("## 2. Overview Performa Perusahaan")
    st.caption("Versi operasional ringkas. Analisis penuh ada di halaman "
               "Analitik.")

    league = metrics.company_league(ts_filtered, min_n=config.MIN_N_RANKING)
    gate_count = metrics.company_league_gate_count(ts_filtered, min_n=config.MIN_N_RANKING)

    # Descriptive lookups for the row subtitle. Not metrics: no rate or count
    # is computed here, only the most common jenis_penempatan per company
    # (a company can span several shipments with different values) and the
    # industry_sector joined from the raw company table by name.
    jenis_lookup = ts_filtered.groupby("company")["jenis_penempatan"].agg(
        lambda s: s.mode().iat[0] if not s.mode().empty else ""
    )
    sektor_lookup = data.company.set_index("company_name")["industry_sector"]

    def _subtitle(company_name):
        jenis = jenis_lookup.get(company_name, "") or "-"
        sektor = sektor_lookup.get(company_name, "") or "-"
        return jenis + " · " + sektor

    def _company_row(row):
        kirim = H._fmt_id(int(row["n"]))
        if not row["lolos_gate"]:
            kirim = kirim + " " + H.badge("n kecil", "warn")
        # ci_width is the full Wilson band (hi - lo), shown as-is in points.
        ci_pct = round(row["ci_width"] * 100)
        rate_text = str(round(row["rate"] * 100, 1)) + "% ±" + str(ci_pct)
        band_html = H.ci_band_cell(
            row["wilson_lo"], row["wilson_center"], row["wilson_hi"], width_px=120
        )
        return (
            '<div style="display:flex;align-items:center;gap:14px;'
            'padding:9px 6px;border-bottom:1px solid ' + WARNA["line"] + ';">'
            + '<div style="flex:1;min-width:0;">'
            + '<div style="font-weight:700;color:' + WARNA["ink"]
            + ';font-size:0.88rem;white-space:nowrap;overflow:hidden;'
            + 'text-overflow:ellipsis;">' + H._esc(row["company"]) + '</div>'
            + '<div style="color:' + WARNA["muted"] + ';font-size:0.74rem;'
            + 'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
            + H._esc(_subtitle(row["company"])) + '</div>'
            + '</div>'
            + '<div style="min-width:76px;text-align:right;font-size:0.8rem;'
            + 'color:' + WARNA["ink2"] + ';white-space:nowrap;">' + kirim + '</div>'
            + '<div>' + band_html + '</div>'
            + '<div style="min-width:92px;text-align:right;font-weight:600;'
            + 'color:' + WARNA["ink"] + ';font-size:0.82rem;white-space:nowrap;">'
            + rate_text + '</div>'
            + '</div>'
        )

    col_title, col_count, col_toggle = st.columns([3, 2, 1.5])
    with col_title:
        st.markdown("#### Acceptance per perusahaan")
    with col_count:
        st.markdown(
            '<div style="padding-top:12px;color:' + WARNA["ink2"]
            + ';font-size:0.85rem;">' + H._fmt_id(gate_count)
            + ' perusahaan, n≥' + str(config.MIN_N_RANKING) + '</div>',
            unsafe_allow_html=True,
        )
    with col_toggle:
        sort_mode = st.radio(
            "Urutkan", ["Tertinggi", "Terendah"], horizontal=True,
            key="perusahaan_sort_toggle", label_visibility="collapsed",
        )

    # Recap only: top 5 by the active sort direction, not the full league.
    top5_league = league.sort_values(
        "rate", ascending=(sort_mode == "Terendah")
    ).head(5).reset_index(drop=True)

    for _, row in top5_league.iterrows():
        st.markdown(_company_row(row), unsafe_allow_html=True)

    # Dynamic example, computed not hardcoded: widest vs narrowest CI band
    # among companies that pass the sample size gate. to_dict() turns the row
    # into plain scalars so int()/round() aren't fed a pandas Scalar union.
    widest = league.loc[league["ci_width"].idxmax()].to_dict()
    gated = league[league["lolos_gate"]]
    narrowest = (
        gated.loc[gated["ci_width"].idxmin()].to_dict() if not gated.empty else widest
    )
    st.caption(
        "Titik = acceptance rate; pita = selang kepercayaan 95% (Wilson). "
        "Pita lebar = sampel kecil, ranking belum bisa dipercaya. Contoh: "
        + str(widest["company"]) + " (n=" + str(int(widest["n"]))
        + ") punya pita ±" + str(round(widest["ci_width"] * 100))
        + ", sedangkan " + str(narrowest["company"]) + " (n="
        + str(int(narrowest["n"])) + ") punya pita ±"
        + str(round(narrowest["ci_width"] * 100)) + "."
    )

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
    # 4. Waktu-respons per perusahaan (Section 6.3, OWNER-DECIDED: Afrizal).
    # Basis send_date, sama seperti jam eskalasi FU/Ghosting (Section 4.5) -
    # bukan last_update/idle_days (Section 4.7), yang basisnya staleness
    # antrean Beranda dan bukan murni sisi perusahaan.
    # =======================================================================
    st.markdown("## 4. Waktu-respons per perusahaan (proses terbuka)")
    st.caption(
        "Rata-rata umur (hari sejak dikirim) proses yang belum selesai per "
        "perusahaan. n >= " + str(config.MIN_N_RANKING) + " untuk lolos gate; "
        "diurutkan dari yang paling lama menunggu."
    )

    response_time = metrics.response_time_per_company(
        ts_filtered, tc_filtered, ANCHOR, min_n=config.MIN_N_RANKING
    )
    response_gated = response_time[response_time["lolos_gate"]].sort_values(
        "avg_response_days", ascending=False
    ).head(10)

    if response_gated.empty:
        st.markdown(
            H.callout(
                "Tidak ada perusahaan dengan proses terbuka yang memenuhi "
                "ambang sampel untuk filter yang aktif saat ini.",
                kind="muted",
            ),
            unsafe_allow_html=True,
        )
    else:
        columns = ["Perusahaan", "Proses terbuka", "Rata-rata respons"]
        align = ["left", "right", "right"]
        rows = []
        for _, r in response_gated.iterrows():
            rows.append([
                r["company"],
                int(r["n"]),
                str(round(r["avg_response_days"], 1)) + " hari",
            ])
        st.markdown(
            H.read_only_table(columns, rows, align=align),
            unsafe_allow_html=True,
        )

    # =======================================================================
    # 5. Status request per perusahaan (BT-05). Draft + response time.
    # =======================================================================
    st.markdown("## 5. Status request per perusahaan")

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
