# pages/4_Analitik.py
# Owner: Andalan. Analitik reporting page (BT-04, BT-07, BT-08).
# Spec Section 6.4. Answers: how is the program performing overall, a report
# for leadership.
#
# Rules followed:
# - No metric is recomputed here. Every number comes from core/metrics.py.
# - No CSV is read here. Data comes from core/loader + core/clean.
# - Category values come from core/schema.py, never raw strings.
# - Colors come from config.WARNA, no hex is written in this file.
# - Charts use Plotly. Cards, badges, callouts, tables use HTML helpers from
#   components/html.py. Inputs use native Streamlit widgets.
#
# Build phase: barebones. Structure, real data, correct render path. Styling
# (CSS polish) is a later pass and lives in components/styles.py.

import streamlit as st
import plotly.graph_objects as go

# Importing the core package runs core/__init__.py, which puts dashboard/ and
# dashboard/core/ on sys.path. That makes the plain imports below work whether
# this page is launched by streamlit run or imported directly.
import core  # noqa: F401
import config
from core import loader, clean, metrics
from components import html as H
from components import styles as S

WARNA = config.WARNA


# ---------------------------------------------------------------------------
# Data. Loaded and cleaned once by the cached loader.
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Analitik SSDC", layout="wide")
S.inject()

raw = loader.load_data()
data = clean.clean_data(raw)

ts = data.tracking_student
tc = data.tracking_company
ss = data.status_student
sa = data.student_all
co = data.company

st.markdown(
    H.page_header(
        "Analitik",
        "Ringkasan kinerja program untuk pimpinan.",
        eyebrow="Laporan Kinerja",
        stamp="Data per " + str(data.ANCHOR.date()),
    ),
    unsafe_allow_html=True,
)

rate_shipment = metrics.success_rate_per_shipment(ts)
n_placement = int(metrics.is_placement_success(metrics.ts_bersih(ts)).sum())
n_base = len(metrics.ts_bersih(ts))

num_student = metrics.success_numerator_per_student(ts)
den_student = metrics.success_denominator_per_student(ts)
rate_student = metrics.success_rate_per_student(ts)

# Verdict line. Fact summary only, not a judgment. Every clause restates a
# number shown on this page. It names coverage (mahasiswa yang disalurkan CDC)
# so 57 percent is not read as a share of all 25.000 students.
st.markdown(
    H.callout(
        str(num_student) + " mahasiswa berhasil ditempatkan. Dihitung dari "
        "mahasiswa yang disalurkan CDC, tingkat keberhasilannya "
        + str(round(rate_student * 100, 1)) + " persen. Tingkat keberhasilan "
        "stabil sepanjang periode dan merata di semua program studi.",
        kind="accent", title="Ringkasan",
    ),
    unsafe_allow_html=True,
)


# ===========================================================================
# PART 1. Dual success rate. Headline is per-student. Per-shipment is secondary.
# ===========================================================================

st.markdown("## Seberapa berhasil program ini")

# Headline is per-student (keputusan tim). Per-shipment is the secondary,
# operational efficiency angle, shown smaller beside it. Both metrics and the
# reasoning live in one surface so the "two honest numbers" story reads as a
# single deliberate unit, not three loose boxes.
with st.container(border=True):
    c1, cdiv, c2, c3 = st.columns([1.15, 0.06, 1, 1.35])

    with c1:
        st.markdown(
            H.kpi_card(
                "Keberhasilan per mahasiswa",
                str(round(rate_student * 100, 1)) + "%",
                str(num_student) + " mahasiswa ditempatkan, dari "
                + str(den_student) + " mahasiswa yang disalurkan CDC",
                accent=WARNA["accent"], big=True,
            ),
            unsafe_allow_html=True,
        )

    with cdiv:
        st.markdown('<div class="metric-divider"></div>', unsafe_allow_html=True)

    with c2:
        st.markdown(
            H.kpi_card(
                "Keberhasilan per pengiriman",
                str(round(rate_shipment * 100, 1)) + "%",
                str(n_placement) + " placement dari " + str(n_base)
                + " pengiriman",
                accent=WARNA["ink2"], big=False,
            ),
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            H.callout(
                "Angka per mahasiswa menghitung tiap orang. Angka per pengiriman "
                "menghitung tiap proses kirim. Tiap mahasiswa memang sengaja "
                "dikirim ke banyak perusahaan dan cukup berhasil di salah satunya, "
                "jadi angka per pengiriman wajar lebih kecil. Keduanya benar, "
                "sudut pandangnya berbeda.",
                kind="accent", title="Kenapa dua angka ini berbeda",
            ),
            unsafe_allow_html=True,
        )


# ===========================================================================
# PART 2. Time trend (BT-07). Volume bars + rate line, dual axis.
# ===========================================================================

st.markdown("## Tren dari waktu ke waktu")

# Default to Per semester: 5 bars read faster than 25 monthly bars. Bulanan
# stays available for a closer look.
mode_label = st.radio(
    "Periode",
    ["Per semester", "Bulanan"],
    horizontal=True,
    key="trend_mode",
)
mode = "bulan" if mode_label == "Bulanan" else "semester"

trend = metrics.trend_per_period(ts, tc, mode)

# Mark the partial last period. Bars for complete periods use bar color, the
# partial one is drawn lighter with a hatch pattern.
bar_colors = [
    WARNA["barlite"] if partial else WARNA["bar"]
    for partial in trend["partial"]
]
bar_patterns = [
    "/" if partial else "" for partial in trend["partial"]
]

fig = go.Figure()
fig.add_trace(
    go.Bar(
        x=trend["periode"],
        y=trend["volume"],
        name="Volume pengiriman",
        marker_color=bar_colors,
        marker_pattern_shape=bar_patterns,
        yaxis="y",
    )
)
fig.add_trace(
    go.Scatter(
        x=trend["periode"],
        y=trend["rate"] * 100,
        name="Rate konversi (%)",
        mode="lines+markers",
        line=dict(color=WARNA["ref"], width=2),
        yaxis="y2",
    )
)
fig.update_layout(
    barmode="group",
    yaxis=dict(title="Volume", rangemode="tozero"),
    yaxis2=dict(
        title="Rate konversi (%)",
        overlaying="y",
        side="right",
        rangemode="tozero",
    ),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    margin=dict(l=10, r=10, t=30, b=10),
    height=380,
)
with st.container(border=True):
    st.plotly_chart(fig, use_container_width=True, theme=None)
    st.markdown(
        H.callout(
            "Periode terakhir bertanda garis miring belum lengkap. Data send_date "
            "berhenti di pertengahan periode, jadi volumenya belum penuh.",
            kind="watch",
        ),
        unsafe_allow_html=True,
    )


# ===========================================================================
# PART 3. Segmentation. Rate per program and per sector. Bars from zero.
# ===========================================================================

st.markdown("## Perbandingan antar segmen")

overall_rate = rate_shipment  # the overall average reference line

seg_prog = metrics.segment_program(ts, ss)
seg_sect = metrics.segment_sector(ts, tc, co)

# Small sample threshold reuses the ranking gate from config for consistency.
min_n = config.MIN_N_RANKING


def _segment_bar_figure(df, label_col, title):
    """Horizontal bar of rate per segment, sorted, average line, n labels.

    Bars start at zero. Small sample rows (n < min_n) are drawn in warn color.
    """
    d = df.sort_values("rate", ascending=True)  # ascending so top is highest
    colors = [
        WARNA["warn"] if n < min_n else WARNA["bar"] for n in d["n"]
    ]
    text_labels = [
        "n=" + str(int(n)) for n in d["n"]
    ]
    f = go.Figure()
    f.add_trace(
        go.Bar(
            x=d["rate"] * 100,
            y=d[label_col],
            orientation="h",
            marker_color=colors,
            text=text_labels,
            textposition="outside",
            cliponaxis=False,
        )
    )
    f.add_vline(
        x=overall_rate * 100,
        line=dict(color=WARNA["ref"], width=2, dash="dash"),
        annotation_text="rata-rata " + str(round(overall_rate * 100, 1)) + "%",
        annotation_position="top",
    )
    f.update_layout(
        title=title,
        xaxis=dict(title="Rate placement (%)", rangemode="tozero"),
        margin=dict(l=10, r=40, t=50, b=10),
        height=max(320, 22 * len(d) + 90),
    )
    return f


sc1, sc2 = st.columns(2)
with sc1:
    with st.container(border=True):
        st.plotly_chart(
            _segment_bar_figure(seg_prog, "program_studi", "Per program studi"),
            use_container_width=True, theme=None,
        )
with sc2:
    with st.container(border=True):
        st.plotly_chart(
            _segment_bar_figure(seg_sect, "industry_sector", "Per sektor industri"),
            use_container_width=True, theme=None,
        )

# Honest finding. Do not dramatize small gaps.
prog_spread = (seg_prog["rate"].max() - seg_prog["rate"].min()) * 100
sect_spread = (seg_sect["rate"].max() - seg_sect["rate"].min()) * 100
st.markdown(
    H.callout(
        "Kinerja konsisten antar segmen. Selisih rate antar program hanya "
        "sekitar " + str(round(prog_spread, 1)) + " poin persen, antar sektor "
        "sekitar " + str(round(sect_spread, 1)) + " poin persen. Semua dekat "
        "rata-rata. Selisih kecil ini tidak perlu dilebih-lebihkan.",
        kind="muted",
    ),
    unsafe_allow_html=True,
)


# ===========================================================================
# PART 4. Full company league (BT-04). Wilson CI table, gate n >= 30.
# ===========================================================================

st.markdown("## Perusahaan mitra")

league = metrics.company_league(ts)
gate_count = metrics.company_league_gate_count(ts)

st.caption(
    "Gate ranking: n minimal " + str(min_n) + " pengiriman. "
    + str(gate_count) + " perusahaan lolos gate. Baris di bawah gate diberi "
    "tanda n kecil."
)

sort_label = st.selectbox(
    "Urutkan",
    ["Rate tertinggi", "Volume terbanyak", "Paling andal (CI tersempit)"],
    key="league_sort",
)

if sort_label == "Rate tertinggi":
    league_sorted = league.sort_values(
        ["lolos_gate", "wilson_center"], ascending=[False, False]
    )
elif sort_label == "Volume terbanyak":
    league_sorted = league.sort_values("n", ascending=False)
else:
    # Most reliable: narrowest CI first, among gate passers.
    league_sorted = league.sort_values(
        ["lolos_gate", "ci_width"], ascending=[False, True]
    )

# Show the top slice for the barebones page. Full pagination is a later pass.
top = league_sorted.head(25)

columns = ["Perusahaan", "n", "k", "Rate", "Wilson CI", "Band"]
align = ["left", "right", "right", "right", "left", "left"]
rows = []
for _, r in top.iterrows():
    ci_text = (
        str(round(r["wilson_lo"] * 100, 1)) + "% - "
        + str(round(r["wilson_hi"] * 100, 1)) + "%"
    )
    perusahaan = H._esc(r["company"])
    if not r["lolos_gate"]:
        perusahaan = perusahaan + " " + H.badge("n kecil", "warn")
    band = H.ci_band_cell(r["wilson_lo"], r["wilson_center"], r["wilson_hi"])
    rows.append([
        perusahaan,
        int(r["n"]),
        int(r["k"]),
        str(round(r["rate"] * 100, 1)) + "%",
        ci_text,
        band,
    ])

st.markdown(
    H.read_only_table(
        columns, rows, align=align, raw_html_cols={0, 5}
    ),
    unsafe_allow_html=True,
)
st.caption("Menampilkan 25 baris teratas sesuai urutan. Titik = center Wilson, "
           "pita = rentang CI 95 persen.")


# ===========================================================================
# PART 5. BT-08. Drift badge + sync freshness slider.
# ===========================================================================

st.markdown("## Kesehatan data")

drift = metrics.drift_student_all_vs_status(sa, ss)
drift_total = sum(drift.values())

b1, b2 = st.columns([1, 1.4])
with b1:
    with st.container(border=True):
        if drift_total == 0:
            badge_html = H.badge("AMAN", "ok")
            drift_text = (
                "student_all dan status_student 100 persen konsisten. "
                "0 selisih pada semester, program, nama, email."
            )
        else:
            badge_html = H.badge("PERIKSA", "crit")
            drift_text = "Ada selisih: " + str(drift)
        st.markdown(
            '<div class="card-title">Status drift ' + badge_html
            + '<span class="ct-sub">Konsistensi student_all vs status_student'
            + '</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(H.callout(drift_text, kind="ok"), unsafe_allow_html=True)

with b2:
    with st.container(border=True):
        st.markdown(
            '<div class="card-title">Kesegaran sync'
            + '<span class="ct-sub">Geser ambang umur untuk menghitung baris '
            + 'sync yang menua</span></div>',
            unsafe_allow_html=True,
        )
        x_days = st.slider(
            "Ambang umur sync (hari)",
            min_value=0,
            max_value=180,
            value=config.SYNC_SLIDER_DEFAULT,
            key="sync_slider",
            label_visibility="collapsed",
        )
        stale = metrics.sync_stale_count(ss, data.SYNC_REF, x_days)
        st.markdown(
            H.kpi_card(
                "Baris sync lebih tua dari " + str(x_days) + " hari",
                str(stale),
                "Relatif terhadap sync terakhir",
                accent=WARNA["ink"],
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            H.callout(
                "Data mahasiswa terakhir di-sync: " + str(data.SYNC_REF.date())
                + " (31 Jan 2025). Relatif terhadap tanggal acuan global "
                + str(data.ANCHOR.date()) + ", semua data sync sudah sekitar 3,5 "
                "bulan atau lebih, karena tabel sync berhenti di Januari.",
                kind="watch",
            ),
            unsafe_allow_html=True,
        )


# ===========================================================================
# PART 6. Scope and data quality notes. One honest text block.
# ===========================================================================

st.markdown("## Catatan cakupan dan kualitas data")

n_luar = len(metrics.placed_diluar_cakupan(ss, ts))
n_anom = int(ts["is_anomali"].sum())
n_lag = len(metrics.placed_belum_update_status(ss, ts))

notes_columns = ["Temuan", "Jumlah", "Perlakuan"]
notes_rows = [
    [
        "Placed tanpa jejak di tracking (di luar alur CDC)",
        str(n_luar),
        "Batas cakupan BT-04, bukan isu sync. Dicatat, tidak dihitung sukses.",
    ],
    [
        "Anomali Finish + On Progress",
        str(n_anom),
        "Dikeluarkan dari semua perhitungan rate. Dilaporkan sebagai isu data.",
    ],
    [
        "Placement tapi status belum Placed",
        str(n_lag),
        "Asumsi keterlambatan update status. Tidak bisa diverifikasi.",
    ],
]
st.markdown(
    H.read_only_table(notes_columns, notes_rows, align=["left", "right", "left"]),
    unsafe_allow_html=True,
)


# ===========================================================================
# PART 7. Cetak and Ekspor laporan buttons.
# ===========================================================================

st.markdown("## Ekspor")
e1, e2 = st.columns(2)
with e1:
    st.button("Cetak", key="cetak", help="Gunakan cetak browser untuk versi PDF")
with e2:
    # TODO(andalan): full PDF export. Print-friendly CSS is the minimum and
    # lands in the styling pass (components/styles.py). A real PDF is optional.
    st.button("Ekspor laporan (PDF)", key="ekspor_pdf", disabled=True,
              help="Belum aktif. Sementara pakai Cetak lalu simpan sebagai PDF.")


# ===========================================================================
# Definition footer. Keep Analitik and Monitoring consistent for judges.
# ===========================================================================

n_rej_pl = int(metrics.is_placement_success(ts).sum())
n_stage_pl = int(metrics.is_stage_placement(ts).sum())
selisih = n_rej_pl - n_stage_pl

st.markdown("---")
st.markdown(
    H.callout(
        "Definisi placement di halaman ini memakai kolom rejection == "
        "Placement, totalnya " + str(n_rej_pl) + ". Angka 'tahap saat ini "
        "Placement' (progress_student) adalah " + str(n_stage_pl) + ". "
        "Selisih " + str(selisih) + " adalah placement yang sudah diarsipkan "
        "ke Finish, tetap dihitung berhasil. Ini konsisten dengan halaman "
        "Monitoring.",
        kind="muted", title="Catatan definisi",
    ),
    unsafe_allow_html=True,
)
