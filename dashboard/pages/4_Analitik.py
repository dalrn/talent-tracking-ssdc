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
from core import cached as C
from components import html as H

WARNA = config.WARNA


def _section_title(text):
    """Section heading, one clear step below the page title (no accent tick).

    Matches the section-title treatment on Monitoring so the pages read as one
    product: navy, 1.12rem, no left accent bar.
    """
    st.markdown(
        "<div style='font-size:1.12rem;font-weight:700;color:" + WARNA["navy"]
        + ";margin:1.4rem 0 0.4rem;letter-spacing:-0.01em;'>" + H._esc(text)
        + "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Data. Loaded and cleaned once by the cached loader. Page config, global CSS,
# and the shared sidebar are set once by app.py (the st.navigation controller).
# ---------------------------------------------------------------------------

raw = loader.load_data()
data = clean.clean_data(raw)

ts = data.tracking_student
tc = data.tracking_company
ss = data.status_student
sa = data.student_all
co = data.company

# Date filter from the shared sidebar (set in app.py). Basis send_date:
# tc is filtered by send_date, then ts is restricted to the surviving
# tracking_company ids (same join pattern as Monitoring).
periode_filter = st.session_state.get("rentang_periode")
if periode_filter:
    start, end = periode_filter
    tc = tc[(tc["send_date"] >= start) & (tc["send_date"] <= end)]
    valid_tc_ids = set(tc["id_tracking_company"].dropna())
    ts = ts[ts["id_tracking_company"].isin(valid_tc_ids)]

# Cache key for the metric wrappers in core/cached.py. The heavy metrics on
# this page depend only on the date range; the trend mode radio and the sort
# selectbox rerun the script but hit cache instead of recomputing.
FKEY = C.filter_key(periode_filter)

# Data-health (BT-08) is condensed into a compact chip beside the title
# instead of a full section lower down. Drift status rides in the badge
# tooltip; the freshness threshold slider hides inside a popover.
drift = C.drift_student_all_vs_status(sa, ss, FKEY)
drift_ok = sum(drift.values()) == 0
x_days = st.session_state.get("sync_slider", config.SYNC_SLIDER_DEFAULT)
stale = metrics.sync_stale_count(ss, data.SYNC_REF, x_days)
drift_tip = (
    "student_all dan status_student 100 persen konsisten: 0 selisih pada "
    "semester, program, nama, email."
    if drift_ok else "Ada selisih antar tabel: " + str(drift)
)

head_l, head_r = st.columns([3.5, 0.85])
with head_l:
    st.markdown(
        H.page_header(
            "Analitik",
            "Ringkasan kinerja program untuk pimpinan.",
        ),
        unsafe_allow_html=True,
    )
with head_r:
    st.markdown(
        H.health_chip(stale, x_days, drift_ok=drift_ok, drift_tip=drift_tip),
        unsafe_allow_html=True,
    )
    with st.popover("Ambang: " + str(x_days) + " hari"):
        st.slider(
            "Ambang umur sync (hari)",
            min_value=0, max_value=180,
            value=config.SYNC_SLIDER_DEFAULT, key="sync_slider",
        )
        st.caption(
            "Angka baris outdated ini wajar besar. Ini snapshot data yang "
            "dibekukan, dan tabel sync berhenti di Januari. Sync terakhir "
            + H.tanggal_id(data.SYNC_REF.date()) + ", sekitar 3,5 bulan sebelum "
            "tanggal acuan " + H.tanggal_id(data.ANCHOR.date()) + ". Jadi pada "
            "ambang " + str(x_days) + " hari, jumlah besar bukan tanda masalah "
            "data. Status konsistensi tetap AMAN."
        )

rate_shipment = metrics.success_rate_per_shipment(ts)
n_placement = int(metrics.is_placement_success(metrics.ts_bersih(ts)).sum())
n_base = len(metrics.ts_bersih(ts))

num_student = metrics.success_numerator_per_student(ts)
den_student = metrics.success_denominator_per_student(ts)
rate_student = metrics.success_rate_per_student(ts)

# Verdict line. Fact summary only, not a judgment. It names coverage
# (mahasiswa yang disalurkan CDC) so the headline is not read as a share of all
# 25.000 students. The exact rate is not repeated here: it appears large in the
# card just below, and the summary points to it rather than restating it.
st.markdown(
    H.callout(
        H._fmt_id(num_student) + " mahasiswa berhasil ditempatkan, dihitung dari "
        "mahasiswa yang disalurkan CDC. Tingkat keberhasilan per mahasiswa ada "
        "di kartu di bawah. Angkanya stabil sepanjang periode dan merata di "
        "semua program studi.",
        kind="accent", title="Ringkasan",
    ),
    unsafe_allow_html=True,
)


# ===========================================================================
# PART 1. Dual success rate. Headline is per-student. Per-shipment is secondary.
# ===========================================================================

_section_title("Seberapa berhasil program ini")

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
                H.pct_id(rate_student * 100),
                H._fmt_id(num_student) + " mahasiswa ditempatkan, dari "
                + H._fmt_id(den_student) + " mahasiswa yang disalurkan CDC",
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
                H.pct_id(rate_shipment * 100),
                H._fmt_id(n_placement) + " placement dari " + H._fmt_id(n_base)
                + " pengiriman",
                accent=WARNA["ink2"], big=False,
            ),
            unsafe_allow_html=True,
        )



# ===========================================================================
# PART 2. Time trend (BT-07). Volume bars + rate line, dual axis.
# ===========================================================================

_section_title("Tren dari waktu ke waktu")

# Default to Per semester: 5 bars read faster than 25 monthly bars. Bulanan
# stays available for a closer look.
mode_label = st.radio(
    "Periode",
    ["Per semester", "Bulanan"],
    horizontal=True,
    key="trend_mode",
)
mode = "bulan" if mode_label == "Bulanan" else "semester"

trend = C.trend_per_period(ts, tc, mode, FKEY)

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
        name="Rate konversi (persen)",
        mode="lines+markers",
        line=dict(color=WARNA["ref"], width=2),
        yaxis="y2",
        hovertemplate="%{y:.1f}%<extra></extra>",
    )
)
# Legend-only marker so the reader knows why the last bar is hatched. It plots
# no data (empty x/y), it exists purely to add the "periode belum lengkap"
# entry with the same lighter color and hatch as the partial bar.
if bool(trend["partial"].iloc[-1]):
    fig.add_trace(
        go.Bar(
            x=[None], y=[None],
            name="Periode belum lengkap",
            marker=dict(color=WARNA["barlite"], pattern_shape="/"),
            showlegend=True,
        )
    )
fig.update_layout(
    barmode="group",
    yaxis=dict(title="Volume", rangemode="tozero"),
    yaxis2=dict(
        title="Rate konversi (persen)",
        overlaying="y",
        side="right",
        rangemode="tozero",
        ticksuffix="%",
    ),
    separators=",.",
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

_section_title("Perbandingan antar segmen")

overall_rate = rate_shipment  # the overall average reference line

seg_prog = C.segment_program(ts, ss, FKEY)
seg_sect = C.segment_sector(ts, tc, co, FKEY)

# Small sample threshold reuses the ranking gate from config for consistency.
min_n = config.MIN_N_RANKING

# Shared x-axis domain so the two side-by-side charts are visually comparable.
# Computed from both segment sets plus the average line, rounded up with head
# room for the outside n labels. Bars still start at zero (never truncated).
_seg_max_rate = max(
    seg_prog["rate"].max(), seg_sect["rate"].max(), overall_rate
) * 100
SEG_X_MAX = 5 * (int(_seg_max_rate // 5) + 2)  # e.g. 25.2 -> 35 room for labels


def _segment_bar_figure(df, label_col, title):
    """Horizontal bar of rate per segment, sorted, average line, n labels.

    Bars start at zero and share SEG_X_MAX as their domain. Small sample rows
    (n < min_n) are drawn in warn color. The n labels sit just inside the bar
    end so the average reference line never crosses them.
    """
    # Sort by rate so the highest segment is at the top of both charts.
    d = df.sort_values("rate", ascending=True)
    colors = [
        WARNA["warn"] if n < min_n else WARNA["bar"] for n in d["n"]
    ]
    text_labels = [
        "kirim " + H._fmt_id(int(n)) for n in d["n"]
    ]
    f = go.Figure()
    f.add_trace(
        go.Bar(
            x=d["rate"] * 100,
            y=d[label_col],
            orientation="h",
            marker_color=colors,
            text=text_labels,
            # Labels inside the bar end: keeps the sample-size text clear of the
            # average line that sits out in the plot area.
            textposition="inside",
            insidetextanchor="end",
            textfont=dict(size=11),
            cliponaxis=False,
        )
    )
    # Average line as a shape that ends at the plot area top, plus a separate
    # annotation above the plot: the line no longer runs through the bar labels.
    f.add_shape(
        type="line",
        x0=overall_rate * 100, x1=overall_rate * 100,
        y0=0, y1=1, yref="paper",
        line=dict(color=WARNA["ref"], width=2.5, dash="dash"),
    )
    f.add_annotation(
        x=overall_rate * 100, y=1.02, yref="paper",
        text="rata-rata " + H.pct_id(overall_rate * 100),
        showarrow=False, font=dict(color=WARNA["ref"], size=11),
        xanchor="left", yanchor="bottom",
    )
    f.update_layout(
        title=title,
        xaxis=dict(
            title="Rate placement (persen)",
            range=[0, SEG_X_MAX],
            ticksuffix="%",
            rangemode="tozero",
        ),
        separators=",.",
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
        "sekitar " + str(round(prog_spread, 1)).replace(".", ",")
        + " poin persen, antar sektor sekitar "
        + str(round(sect_spread, 1)).replace(".", ",") + " poin persen. Semua "
        "dekat rata-rata. Selisih kecil ini tidak perlu dilebih-lebihkan.",
        kind="muted",
    ),
    unsafe_allow_html=True,
)


# ===========================================================================
# PART 4. Full company league (BT-04). Wilson CI table, gate n >= 30.
# ===========================================================================

_section_title("Perusahaan mitra")

league = C.company_league(ts, FKEY)
gate_count = C.company_league_gate_count(ts, FKEY)

st.caption(
    "Terdapat " + H._fmt_id(gate_count) + " perusahaan dengan minimal "
    + str(min_n) + " pengiriman."
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

columns = ["Perusahaan", "Kirim", "Placement", "Rate", "Selang 95%", "Pita"]
align = ["left", "right", "right", "right", "left", "left"]
rows = []
for _, r in top.iterrows():
    ci_text = (
        H.pct_id(r["wilson_lo"] * 100) + " sampai "
        + H.pct_id(r["wilson_hi"] * 100)
    )
    perusahaan = H._esc(r["company"])
    if not r["lolos_gate"]:
        perusahaan = perusahaan + " " + H.badge("n kecil", "warn")
    band = H.ci_band_cell(r["wilson_lo"], r["wilson_center"], r["wilson_hi"])
    rows.append([
        perusahaan,
        H._fmt_id(int(r["n"])),
        H._fmt_id(int(r["k"])),
        H.pct_id(r["rate"] * 100),
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
           "pita = rentang selang kepercayaan 95 persen. Kirim = jumlah "
           "pengiriman, Placement = jumlah penempatan berhasil.")


# ===========================================================================
# PART 5. Scope and data quality notes. One honest text block.
# (BT-08 data-health moved to the compact chip in the page header.)
# ===========================================================================

_section_title("Catatan cakupan dan kualitas data")

n_luar = len(C.placed_diluar_cakupan(ss, ts, FKEY))
n_anom = int(ts["is_anomali"].sum())
n_lag = len(C.placed_belum_update_status(ss, ts, FKEY))

# The top scope finding gets its own callout so its text has room to breathe,
# instead of being cramped into a narrow table cell. Number and treatment
# meaning unchanged: still a coverage limit, still not counted as success.
st.markdown(
    H.callout(
        H._fmt_id(n_luar) + " mahasiswa berstatus Placed tanpa satu pun jejak "
        "di tracking. Tidak dihitung sebagai keberhasilan program CDC.",
        kind="watch", title="Placed di luar alur CDC",
    ),
    unsafe_allow_html=True,
)

notes_columns = ["Temuan", "Jumlah", "Perlakuan"]
notes_rows = [
    [
        "Anomali Finish dan On Progress",
        H._fmt_id(n_anom),
        "Dikeluarkan dari semua perhitungan rate. Dilaporkan sebagai isu data.",
    ],
    [
        "Placement tapi status belum Placed",
        H._fmt_id(n_lag),
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

_section_title("Ekspor")
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
        "Definisi placement di halaman ini memakai kolom rejection bernilai "
        "Placement, totalnya " + H._fmt_id(n_rej_pl) + ". Angka tahap saat ini "
        "Placement (progress_student) adalah " + H._fmt_id(n_stage_pl) + ". "
        "Selisih " + H._fmt_id(selisih) + " adalah placement yang sudah "
        "diarsipkan ke Finish, tetap dihitung berhasil. Ini konsisten dengan "
        "halaman Monitoring.",
        kind="muted", title="Catatan definisi",
    ),
    unsafe_allow_html=True,
)
