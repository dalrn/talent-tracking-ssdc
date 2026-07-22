# components/html.py
# Owner: shared. HTML generators for KPI cards, badges, callouts, and
# read-only tables. See spec Section 6.
#
# These are generic. Any page (Analitik, Matching, Monitoring, Beranda) can
# call them. They return HTML strings for st.markdown(..., unsafe_allow_html=True).
# Colors come from config.WARNA. No page specific content is baked in.
#
# Build phase note: this is barebones. Structure and hooks are here, with
# light inline style only. Full CSS lives in components/styles.py and comes
# in the styling pass. Class names are stable so styles.py can target them.

import html as _html

import config

WARNA = config.WARNA


def _esc(value):
    """Escape a value for safe HTML text. None becomes an empty string."""
    if value is None:
        return ""
    return _html.escape(str(value))


def kpi_card(title, value, subtitle="", accent=None, big=False):
    """A single KPI card. Title on top, big value, optional subtitle.

    accent is a WARNA hex used for the value color. big enlarges the value
    for a headline card. Returns an HTML string.
    Generic: any page can use it for any metric.
    """
    accent = accent or WARNA["ink"]
    value_size = "2.4rem" if big else "1.8rem"
    return (
        '<div class="kpi-card" style="border:1px solid ' + WARNA["line"]
        + ';background:' + WARNA["panel"] + ';padding:14px 16px;'
        + 'border-radius:8px;">'
        + '<div class="kpi-title" style="color:' + WARNA["muted"]
        + ';font-size:0.8rem;">' + _esc(title) + '</div>'
        + '<div class="kpi-value" style="color:' + accent
        + ';font-size:' + value_size + ';font-weight:700;line-height:1.1;">'
        + _esc(value) + '</div>'
        + '<div class="kpi-sub" style="color:' + WARNA["ink2"]
        + ';font-size:0.8rem;">' + _esc(subtitle) + '</div>'
        + '</div>'
    )


def badge(text, kind="muted"):
    """A small inline badge. kind picks the color pair from WARNA.

    kind: ok, warn, watch, crit, hot, muted, accent. Returns an HTML string.
    Used for small sample flags, AMAN state, tanpa CV, and so on.
    """
    fg_map = {
        "ok": WARNA["ok"], "warn": WARNA["warn"], "watch": WARNA["watch"],
        "crit": WARNA["crit"], "hot": WARNA["hot"], "accent": WARNA["accent"],
        "muted": WARNA["muted"],
    }
    bg_map = {
        "ok": WARNA["ok_bg"], "warn": WARNA["warn_bg"], "watch": WARNA["watch_bg"],
        "crit": WARNA["crit_bg"], "hot": WARNA["hot_bg"], "accent": WARNA["page"],
        "muted": WARNA["page"],
    }
    fg = fg_map.get(kind, WARNA["muted"])
    bg = bg_map.get(kind, WARNA["page"])
    return (
        '<span class="badge badge-' + kind + '" style="color:' + fg
        + ';background:' + bg + ';border:1px solid ' + fg
        + ';padding:1px 7px;border-radius:10px;font-size:0.72rem;'
        + 'white-space:nowrap;">' + _esc(text) + '</span>'
    )


def callout(text, kind="accent", title=None):
    """A boxed note. kind sets the left border and tint. Returns HTML.

    Used for the "why they differ" panel, honest captions, definition footer.
    """
    fg_map = {
        "ok": WARNA["ok"], "warn": WARNA["warn"], "watch": WARNA["watch"],
        "crit": WARNA["crit"], "hot": WARNA["hot"], "accent": WARNA["accent"],
        "muted": WARNA["ink2"],
    }
    bg_map = {
        "ok": WARNA["ok_bg"], "warn": WARNA["warn_bg"], "watch": WARNA["watch_bg"],
        "crit": WARNA["crit_bg"], "hot": WARNA["hot_bg"], "accent": WARNA["page"],
        "muted": WARNA["panel"],
    }
    fg = fg_map.get(kind, WARNA["accent"])
    bg = bg_map.get(kind, WARNA["page"])
    title_html = ""
    if title:
        title_html = (
            '<div class="callout-title" style="font-weight:700;color:' + fg
            + ';margin-bottom:4px;">' + _esc(title) + '</div>'
        )
    return (
        '<div class="callout callout-' + kind + '" style="border-left:4px solid '
        + fg + ';background:' + bg + ';padding:10px 14px;border-radius:6px;'
        + 'color:' + WARNA["ink"] + ';font-size:0.85rem;">'
        + title_html + _esc(text) + '</div>'
    )


def read_only_table(columns, rows, align=None, raw_html_cols=None):
    """Render a read-only HTML table. Returns an HTML string.

    columns: list of header labels.
    rows: list of row lists, each cell a string or number.
    align: optional list of "left"/"right"/"center" per column.
    raw_html_cols: optional set of column indexes whose cells are already
    HTML (for example a badge or a CI band) and must not be escaped.

    Generic: the Wilson league, the notes table, any read-only grid.
    """
    align = align or ["left"] * len(columns)
    raw_html_cols = raw_html_cols or set()

    head_cells = "".join(
        '<th style="text-align:' + align[i] + ';border-bottom:2px solid '
        + WARNA["line"] + ';padding:6px 10px;color:' + WARNA["ink2"]
        + ';font-size:0.78rem;">' + _esc(col) + '</th>'
        for i, col in enumerate(columns)
    )

    body_rows = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            content = str(cell) if i in raw_html_cols else _esc(cell)
            cells.append(
                '<td style="text-align:' + align[i]
                + ';padding:5px 10px;border-bottom:1px solid ' + WARNA["line"]
                + ';font-size:0.82rem;color:' + WARNA["ink"] + ';">'
                + content + '</td>'
            )
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    return (
        '<table class="ro-table" style="border-collapse:collapse;width:100%;'
        + 'background:' + WARNA["panel"] + ';">'
        + '<thead><tr>' + head_cells + '</tr></thead>'
        + '<tbody>' + "".join(body_rows) + '</tbody></table>'
    )


def ci_band_cell(lo, center, hi, width_px=140):
    """A small horizontal Wilson CI band as inline HTML. Returns a string.

    Draws a track from 0 to 1, a light band from lo to hi (barlite), and a
    point marker at center (bar). Used in the company league table.
    Values are proportions in 0 to 1.
    """
    def pct(x):
        return str(round(max(0.0, min(1.0, x)) * 100, 1))

    band_left = pct(lo)
    band_w = str(round((min(1.0, hi) - max(0.0, lo)) * 100, 1))
    point_left = pct(center)
    return (
        '<div class="ci-band" style="position:relative;width:' + str(width_px)
        + 'px;height:14px;background:' + WARNA["page"] + ';border:1px solid '
        + WARNA["line"] + ';border-radius:3px;">'
        + '<div style="position:absolute;left:' + band_left + '%;width:'
        + band_w + '%;top:0;bottom:0;background:' + WARNA["barlite"] + ';"></div>'
        + '<div style="position:absolute;left:' + point_left
        + '%;top:-1px;bottom:-1px;width:2px;background:' + WARNA["bar"]
        + ';"></div>'
        + '</div>'
    )
