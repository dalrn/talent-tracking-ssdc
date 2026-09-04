# components/styles.py
# Owner: shared, styling phase. The global CSS layer for the whole app.
#
# One entry point: inject(). Call it once near the top of every page (and
# app.py), right after st.set_page_config. It emits a single <style> block
# built from config.WARNA, so the palette stays single-sourced.
#
# Design intent (competition-grade "refined light"):
#   - Typography: Inter, a real type scale, tabular numerals for figures.
#   - Chrome: kill the default Streamlit top bar, tighten the page frame.
#   - Native widgets: repaint the leftover red bits, soften inputs.
#   - Components: the KPI cards, callouts, badges, tables, and funnel rows
#     from components/html.py keep their stable class names; here we add
#     elevation, hover, and rhythm on top of their inline base styles.
#
# This module changes presentation only. It reads no data and computes no
# metric. If plotly is installed, it also registers a matching chart theme
# (see plotly template block at the bottom) so figures inherit the palette
# without any per-figure edits.

import streamlit as st

import config

WARNA = config.WARNA


def _root_vars():
    """Emit the :root CSS custom properties, palette from WARNA plus tokens."""
    w = WARNA
    return (
        ":root{"
        # palette, mirrored from config.WARNA so CSS and Python share one source
        "--c-navy:" + w["navy"] + ";"
        "--c-gold:" + w["gold"] + ";--c-gold-bg:" + w["gold_bg"] + ";"
        "--c-accent:" + w["accent"] + ";"
        "--c-bar:" + w["bar"] + ";--c-barlite:" + w["barlite"] + ";"
        "--c-ref:" + w["ref"] + ";"
        "--c-ink:" + w["ink"] + ";--c-ink2:" + w["ink2"] + ";--c-muted:" + w["muted"] + ";"
        "--c-line:" + w["line"] + ";--c-panel:" + w["panel"] + ";--c-page:" + w["page"] + ";"
        "--c-ok:" + w["ok"] + ";--c-ok-bg:" + w["ok_bg"] + ";"
        "--c-warn:" + w["warn"] + ";--c-warn-bg:" + w["warn_bg"] + ";"
        "--c-watch:" + w["watch"] + ";--c-watch-bg:" + w["watch_bg"] + ";"
        "--c-crit:" + w["crit"] + ";--c-crit-bg:" + w["crit_bg"] + ";"
        "--c-hot:" + w["hot"] + ";--c-hot-bg:" + w["hot_bg"] + ";"
        # design tokens
        "--radius:14px;--radius-sm:10px;--radius-xs:8px;"
        "--shadow-sm:0 1px 2px rgba(20,24,26,.04),0 1px 3px rgba(20,24,26,.05);"
        "--shadow-md:0 4px 14px -4px rgba(20,24,26,.10),0 2px 6px -3px rgba(20,24,26,.07);"
        "--shadow-lg:0 18px 40px -12px rgba(15,95,102,.18),0 8px 18px -10px rgba(20,24,26,.12);"
        "--ring:0 0 0 3px rgba(15,95,102,.16);"
        "--font:'Inter','Segoe UI',system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;"
        "}"
    )


# The static stylesheet. Kept as one string for a single injection. Selectors
# lean on Streamlit's stable data-testid hooks; where those shift between
# versions we also match the friendlier class names, so a miss degrades
# gracefully to the config.toml theme rather than breaking anything.
_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ---- Typography base -------------------------------------------------- */
html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"]{
  font-family: var(--font);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  color: var(--c-ink);
}
.stApp{ background: var(--c-page); }

/* Numerals: line them up wherever figures live. */
.kpi-value, .ro-table td, .ci-band, .funnel-row, [data-testid="stMetricValue"]{
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum' 1, 'cv01' 1, 'ss01' 1;
}

/* Headings: navy brand color, tighter than the Streamlit default. No rule
   line under h2 (that read as blocky); the accent tick carries the rhythm. */
h1, h2, h3, h4{ color: var(--c-navy); letter-spacing: -0.015em; font-weight: 700; }
h1{ font-size: 2.15rem; font-weight: 800; line-height: 1.12; }
h2{ font-size: 1.42rem; margin-top: 2rem; }
h3{ font-size: 1.12rem; margin-top: 1.1rem; }
h4{ font-size: .98rem; color: var(--c-ink2); }
/* Accent tick before section headers (h2) for a branded rhythm. */
[data-testid="stMarkdownContainer"] h2{ position: relative; padding-left: 14px; }
[data-testid="stMarkdownContainer"] h2::before{
  content:""; position:absolute; left:0; top:.14em; bottom:.18em; width:4px;
  border-radius:3px; background: var(--c-navy);
}

/* ---- Page frame & chrome --------------------------------------------- */
/* Remove the default top header bar; reclaim the space. */
[data-testid="stHeader"]{ background: transparent; height: 0; }
[data-testid="stToolbar"]{ right: .6rem; }
#MainMenu, [data-testid="stStatusWidget"]{ visibility: hidden; }
footer{ visibility: hidden; }
/* Comfortable, centered reading measure instead of edge-to-edge sprawl. */
.block-container, [data-testid="stMainBlockContainer"]{
  padding-top: 2.6rem; padding-bottom: 4rem;
  max-width: 1360px;
}

/* ---- Sidebar ---------------------------------------------------------- */
[data-testid="stSidebar"]{
  background: linear-gradient(180deg,#fbfcfb 0%, #f1f4f2 100%);
  border-right: 1px solid var(--c-line);
}
[data-testid="stSidebar"] [data-testid="stSidebarNav"]{ padding-top: .4rem; }
/* Nav links: pill hover, teal active state (replaces the grey block). */
[data-testid="stSidebarNav"] a{
  border-radius: 9px; margin: 1px 6px; padding: .28rem .6rem;
  transition: background .15s ease, color .15s ease;
}
[data-testid="stSidebarNav"] a:hover{ background: rgba(15,95,102,.07); }
[data-testid="stSidebarNav"] a[aria-current="page"]{
  background: rgba(15,95,102,.12);
}
[data-testid="stSidebarNav"] a[aria-current="page"] span{
  color: var(--c-accent) !important; font-weight: 600;
}

/* ---- Buttons ---------------------------------------------------------- */
.stButton > button, .stLinkButton > a, .stDownloadButton > button{
  border-radius: var(--radius-xs);
  font-weight: 600;
  border: 1px solid var(--c-line);
  transition: transform .08s ease, box-shadow .15s ease, background .15s ease,
              border-color .15s ease;
  box-shadow: var(--shadow-sm);
}
.stButton > button:hover, .stLinkButton > a:hover, .stDownloadButton > button:hover{
  border-color: var(--c-accent);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
.stButton > button:active{ transform: translateY(0); }
/* Primary (e.g. the selected Beranda segment) gets the teal, not the red. */
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"]{
  background: linear-gradient(180deg,var(--c-accent),#0c5057);
  border-color: transparent; color: #fff;
  box-shadow: 0 2px 8px -1px rgba(15,95,102,.35);
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover{
  filter: brightness(1.06);
}

/* ---- Tabs ------------------------------------------------------------- */
.stTabs [data-baseweb="tab-list"]{ gap: 4px; border-bottom: 1px solid var(--c-line); }
.stTabs [data-baseweb="tab"]{
  font-weight: 600; color: var(--c-muted); padding: .35rem .1rem;
}
.stTabs [aria-selected="true"]{ color: var(--c-accent); }
.stTabs [data-baseweb="tab-highlight"]{ background: var(--c-accent); height: 3px; border-radius: 3px; }

/* ---- Inputs (text, select, searchbox) -------------------------------- */
[data-baseweb="input"], [data-baseweb="select"] > div, .stTextInput input{
  border-radius: var(--radius-xs) !important;
}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within{
  box-shadow: var(--ring) !important; border-color: var(--c-accent) !important;
}
[data-testid="stTextInputRootElement"]{ border-radius: var(--radius-xs); }

/* ---- Dataframe: the biggest remaining "vanilla" tell ----------------- */
[data-testid="stDataFrame"], [data-testid="stDataFrameResizable"]{
  border: 1px solid var(--c-line);
  border-radius: var(--radius-sm);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}
[data-testid="stDataFrame"] [role="columnheader"]{
  text-transform: uppercase; letter-spacing: .04em;
  font-size: .68rem !important; font-weight: 700;
}

/* ---- KPI cards (.kpi-card from components/html.py) ------------------- */
/* html.py sets a hairline border + flat panel inline; upgrade to elevated
   cards with a top accent hairline and a hover lift. !important beats the
   inline border only where it must. */
/* Flat typographic stat, not a box. No border, no shadow, no fill: a navy
   left rule delineates it on the white canvas. */
.kpi-card{
  border: none !important;
  border-left: 3px solid var(--c-navy) !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
  padding: 2px 0 2px 16px !important;
  position: relative;
}
.kpi-card::before{ display: none; }
.kpi-title{
  text-transform: uppercase; letter-spacing: .05em;
  font-weight: 600 !important; font-size: .72rem !important;
}
.kpi-value{ letter-spacing: -0.02em; margin: 2px 0 1px; }

/* ---- Callouts (.callout) --------------------------------------------- */
.callout{
  border-radius: var(--radius-sm) !important;
  box-shadow: var(--shadow-sm);
  line-height: 1.5;
  padding: 13px 16px !important;
}
.callout-title{ letter-spacing: -0.01em; }

/* ---- Badges (.badge) -------------------------------------------------- */
.badge{
  font-weight: 600 !important; letter-spacing: .02em;
  border-radius: 999px !important; padding: 2px 9px !important;
}

/* ---- Read-only tables (.ro-table) ------------------------------------ */
.ro-table{ border-radius: var(--radius-sm); overflow: hidden; box-shadow: var(--shadow-sm); }
.ro-table th{
  text-transform: uppercase !important; letter-spacing: .04em;
  font-size: .68rem !important; font-weight: 700 !important;
  background: #f7f9f8; position: sticky; top: 0;
}
.ro-table tbody tr{ transition: background .12s ease; }
.ro-table tbody tr:nth-child(even) td{ background: #fafbfa; }
.ro-table tbody tr:hover td{ background: var(--c-hot-bg); }

/* ---- Funnel rows (.funnel-row) --------------------------------------- */
.funnel-row{ border-radius: var(--radius-xs); padding: 10px 8px !important; transition: background .12s ease; }
.funnel-row:hover{ background: #f7f9f8; }

/* ---- Misc ------------------------------------------------------------- */
hr, [data-testid="stMarkdownContainer"] hr{
  border: none; border-top: 1px solid var(--c-line); margin: 1.6rem 0;
}
/* The Streamlit "st.caption" grey used across the pages, a touch softer. */
[data-testid="stCaptionContainer"]{ color: var(--c-muted); }

/* ---- Layout primitives ----------------------------------------------- */
/* KPI cards: a floor height + vertical centering so cards in a row align
   instead of stair-stepping when subtitles differ in length. */
.kpi-card{ min-height: 132px; display: flex; flex-direction: column; justify-content: center; }

/* Grouping containers stay flat: no box. Content is separated by whitespace
   and the section tick, not outlines. This is the navy-and-white look. */
[data-testid="stVerticalBlockBorderWrapper"]{
  background: transparent;
  border: none !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}
[data-testid="stVerticalBlockBorderWrapper"] .kpi-card{ padding-left: 16px !important; }
[data-testid="stVerticalBlockBorderWrapper"] .callout{ box-shadow: none; }

/* A soft vertical divider between metrics inside one surface. */
.metric-divider{
  border-left: 1px solid var(--c-line); height: 100%; min-height: 64px;
  margin: 0 auto; width: 0;
}

/* Section eyebrow used inside surfaces (html.card_title). */
.card-title{ font-size: .96rem; font-weight: 700; color: var(--c-ink);
  letter-spacing: -0.01em; margin: 0 0 2px; }
.card-title .ct-sub{ display:block; font-weight:500; color:var(--c-muted);
  font-size:.76rem; letter-spacing:0; margin-top:3px; }

/* ---- Page header component (.page-header from html.page_header) ------- */
.page-header{ margin: 0 0 1.4rem; }
.page-header .ph-eyebrow{
  text-transform: uppercase; letter-spacing: .14em; font-size: .7rem;
  font-weight: 700; color: var(--c-accent); margin-bottom: 6px;
}
.page-header .ph-title{
  font-size: 2.15rem; font-weight: 800; letter-spacing: -0.02em;
  line-height: 1.1; color: var(--c-navy);
}
.page-header .ph-sub{
  color: var(--c-ink2); font-size: .92rem; margin-top: 8px; max-width: 70ch;
  line-height: 1.5;
}
.page-header .ph-stamp{
  display:inline-block; margin-top: 10px; font-size: .74rem; font-weight: 600;
  color: var(--c-ink2); background: var(--c-panel); border: 1px solid var(--c-line);
  border-radius: 999px; padding: 3px 11px; box-shadow: var(--shadow-sm);
}

/* ---- Compact data-health widget (html.health_chip) ------------------- */
/* Sits in the top-right beside the page title. Condenses the whole
   "Kesehatan data" section into one small navy-rule stat. */
/* Self-contained status panel, not a heading: no navy accent bar, a hairline
   border and panel fill set it apart from the section titles. The count is a
   frozen-snapshot artifact, so it is small and neutral; the AMAN badge, not
   the number, carries the status. */
.health-chip{
  border: 1px solid var(--c-line); background: var(--c-panel);
  border-radius: 8px; padding: 8px 12px; margin-top: 4px;
}
.health-chip .hc-top{ display:flex; align-items:center; gap:8px; margin-bottom: 3px; }
.health-chip .hc-label{
  text-transform: uppercase; letter-spacing: .05em; font-size: .64rem;
  font-weight: 700; color: var(--c-muted);
}
.health-chip .hc-badge{
  font-weight: 700; font-size: .62rem; letter-spacing: .03em;
  border-radius: 999px; padding: 1px 8px; cursor: help;
  color: var(--c-ok); background: var(--c-ok-bg); border: 1px solid var(--c-ok);
}
.health-chip .hc-badge.warn{ color: var(--c-crit); background: var(--c-crit-bg); border-color: var(--c-crit); }
.health-chip .hc-main{ display:flex; align-items:baseline; gap:6px; }
.health-chip .hc-value{
  font-size: .95rem; font-weight: 600; line-height: 1; color: var(--c-ink2);
  letter-spacing: -0.01em; font-variant-numeric: tabular-nums;
}
.health-chip .hc-unit{ color: var(--c-muted); font-size: .72rem; font-weight: 500; }

/* Threshold popover: quiet text-link trigger, and a narrow content panel. */
[data-testid="stPopover"] button{
  border: none !important; box-shadow: none !important; background: transparent !important;
  color: var(--c-accent) !important; font-size: .76rem !important; font-weight: 600 !important;
  padding: 2px 0 0 14px !important;
}
[data-testid="stPopover"] button:hover{ text-decoration: underline; transform: none; }
[data-testid="stPopoverBody"], div[data-baseweb="popover"] [data-testid="stVerticalBlock"]{
  max-width: 320px;
}

/* ---- Cetak -------------------------------------------------------------
   Tombol Cetak di Analitik memanggil dialog cetak peramban, jadi tampilan
   cetak perlu diatur: chrome aplikasi (sidebar, toolbar, tombol) tidak ikut
   tercetak, kanvas memakai lebar penuh kertas, dan panel tidak terpotong di
   pergantian halaman. */
@media print{
  /* Chrome aplikasi yang tidak ada artinya di atas kertas. */
  [data-testid="stSidebar"],
  [data-testid="stSidebarCollapsedControl"],
  [data-testid="stHeader"],
  [data-testid="stToolbar"],
  [data-testid="stStatusWidget"],
  [data-testid="stAppDeployButton"],
  .stButton, .stDownloadButton, [data-testid="stPopover"]{
    display: none !important;
  }

  /* Kanvas memakai seluruh lebar kertas, tanpa sisa margin aplikasi. */
  [data-testid="stAppViewContainer"], .main, .block-container,
  [data-testid="stMainBlockContainer"]{
    margin: 0 !important;
    padding: 0 !important;
    max-width: 100% !important;
    width: 100% !important;
  }

  /* Warna latar dan aksen ikut tercetak, bukan dibuang peramban. */
  *{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }

  /* Jangan memotong panel, kartu, tabel, atau grafik di tengah halaman. */
  [data-testid="stVerticalBlockBorderWrapper"], .kpi-card, .callout,
  table, .stPlotlyChart{
    break-inside: avoid;
    page-break-inside: avoid;
  }

  /* Judul tidak berdiri sendiri di kaki halaman. */
  h1, h2, h3{ break-after: avoid; page-break-after: avoid; }
}
"""


def inject():
    """Inject the global stylesheet. Call once per page after set_page_config.

    Idempotent within a run: Streamlit reruns the whole script top to bottom,
    so calling this at the top of each page paints the styles exactly once.
    """
    st.markdown(
        "<style>" + _root_vars() + _CSS + "</style>",
        unsafe_allow_html=True,
    )
    _register_plotly_theme()


# ---------------------------------------------------------------------------
# Plotly theme. Registered so figures inherit the palette and a clean look
# (Inter font, faint grid, no chart junk) without per-figure edits. Pages that
# do not use plotly never trigger this because the import is guarded.
# ---------------------------------------------------------------------------

_PLOTLY_DONE = False


def _register_plotly_theme():
    global _PLOTLY_DONE
    if _PLOTLY_DONE:
        return
    try:
        import plotly.io as pio
        import plotly.graph_objects as go
    except Exception:
        _PLOTLY_DONE = True
        return

    w = WARNA
    template = go.layout.Template(
        layout=dict(
            font=dict(
                family="Inter, Segoe UI, system-ui, sans-serif",
                color=w["ink"], size=13,
            ),
            title=dict(font=dict(size=15, color=w["ink"]), x=0, xanchor="left"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=[w["bar"], w["ref"], w["accent"], w["hot"], w["ok"], w["watch"]],
            xaxis=dict(
                gridcolor="rgba(20,24,26,0.06)", zeroline=False,
                linecolor=w["line"], ticks="outside", tickcolor=w["line"],
                title=dict(font=dict(size=12, color=w["ink2"])),
            ),
            yaxis=dict(
                gridcolor="rgba(20,24,26,0.06)", zeroline=False,
                linecolor=w["line"], ticks="outside", tickcolor=w["line"],
                title=dict(font=dict(size=12, color=w["ink2"])),
            ),
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                font=dict(size=12, color=w["ink2"]),
            ),
            hoverlabel=dict(
                bgcolor=w["panel"], bordercolor=w["line"],
                font=dict(family="Inter, sans-serif", color=w["ink"], size=12),
            ),
            margin=dict(l=10, r=10, t=36, b=10),
        )
    )
    pio.templates["ssdc"] = template
    # Compose with plotly_white so anything we did not set still looks clean.
    pio.templates.default = "plotly_white+ssdc"
    _PLOTLY_DONE = True
