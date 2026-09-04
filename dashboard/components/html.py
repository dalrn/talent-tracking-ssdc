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


def _fmt_id(n):
    """Format an integer with Indonesian thousands separators (dots)."""
    return "{:,}".format(int(n)).replace(",", ".")


_BULAN_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def tanggal_id(d):
    """Format a date as '17 Mei 2025' (Indonesian long form)."""
    return str(d.day) + " " + _BULAN_ID[d.month - 1] + " " + str(d.year)


def pct_id(value, decimals=1):
    """Format a percent with an Indonesian decimal comma, e.g. '22,9%'.

    value is already a percentage number (22.9), not a fraction. decimals=0
    drops the decimal part entirely.
    """
    text = ("{:." + str(decimals) + "f}").format(value)
    return text.replace(".", ",") + "%"


def page_header(title, subtitle="", eyebrow="", stamp=None):
    """The page masthead. Replaces a bare st.title + st.caption.

    eyebrow is a small uppercase kicker above the title. It is off by default;
    pass a non-empty string only if a page wants one. stamp is an optional pill
    (used for the "Data per <date>" freshness note). Styled by the .page-header
    rules in components/styles.py. Returns HTML.
    """
    eyebrow_html = ""
    if eyebrow:
        eyebrow_html = '<div class="ph-eyebrow">' + _esc(eyebrow) + '</div>'
    sub_html = ""
    if subtitle:
        sub_html = '<div class="ph-sub">' + _esc(subtitle) + '</div>'
    stamp_html = ""
    if stamp:
        stamp_html = '<div class="ph-stamp">' + _esc(stamp) + '</div>'
    return (
        '<div class="page-header">'
        + eyebrow_html
        + '<div class="ph-title">' + _esc(title) + '</div>'
        + sub_html
        + stamp_html
        + '</div>'
    )


def health_chip(stale, x_days, drift_ok=True, drift_tip="", label="Kesehatan data"):
    """Compact data-health widget for the top-right of a page header.

    Condenses the drift status and the stale-sync count into one small stat.
    stale is the count of sync rows older than x_days. drift_ok picks the AMAN
    (green) vs PERLU DICEK (red) badge; drift_tip is the hover tooltip that carries
    the full explanation so no space is spent on it. Styled by .health-chip in
    components/styles.py. Returns an HTML string.
    """
    badge_cls = "hc-badge" if drift_ok else "hc-badge warn"
    badge_txt = "AMAN" if drift_ok else "PERLU DICEK"
    return (
        '<div class="health-chip">'
        + '<div class="hc-top">'
        + '<span class="hc-label">' + _esc(label) + '</span>'
        + '<span class="' + badge_cls + '" title="' + _esc(drift_tip) + '">'
        + badge_txt + '</span>'
        + '</div>'
        + '<div class="hc-main">'
        + '<span class="hc-value">' + _fmt_id(stale) + '</span>'
        + '<span class="hc-unit">data belum diperbarui</span>'
        + '</div>'
        + '</div>'
    )


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


def funnel_bar(label, sublabel, aktif, gugur=0, gugur_label="",
                accent=None, is_placement=False, max_val=None):
    """One funnel stage row: label/sublabel plus an active+drop bar (Section 4.13).

    aktif is the active count (progress_student) for this stage. gugur is the
    drop count at this stage's gate (rejection), 0 for stages with no gate
    (CDC Briefing) or for the terminal Placement stage. Bar widths are
    percentages of max_val so every stage in the funnel is drawn to one
    shared scale instead of each bar filling its own row - pass the largest
    (aktif + gugur) across the funnel as max_val. Absolute numbers only, no
    percent-of-initial, since the stage counts are not monotonic (Section
    4.13 problem 2). Returns an HTML string; the "Buka" button is a native
    st.button the caller renders alongside this markup.
    """
    accent = accent or WARNA["bar"]
    active_color = WARNA["ok"] if is_placement else accent
    scale = max_val if max_val else max(aktif + gugur, 1)

    aktif_pct = round(aktif / scale * 100, 2) if scale else 0
    gugur_pct = round(gugur / scale * 100, 2) if scale else 0

    aktif_text = _fmt_id(aktif) + (" ditempatkan" if is_placement else "")
    active_radius = "4px 0 0 4px" if gugur > 0 else "4px"

    bar_html = (
        '<div style="display:flex;align-items:stretch;height:34px;width:100%;">'
        + '<div style="width:' + str(aktif_pct) + '%;min-width:2px;background:'
        + active_color + ';color:#fff;display:flex;align-items:center;'
        + 'padding:0 10px;font-weight:700;font-size:0.85rem;white-space:nowrap;'
        + 'overflow:hidden;border-radius:' + active_radius + ';">'
        + _esc(aktif_text) + '</div>'
    )
    if gugur > 0:
        bar_html += (
            '<div style="width:' + str(gugur_pct) + '%;min-width:2px;background:'
            + WARNA["ref"] + ';color:' + WARNA["ink"] + ';display:flex;'
            + 'align-items:center;padding:0 10px;font-size:0.78rem;'
            + 'white-space:nowrap;overflow:hidden;border-radius:0 4px 4px 0;">'
            + _esc(_fmt_id(gugur)) + ' ' + _esc(gugur_label) + '</div>'
        )
    bar_html += '</div>'

    return (
        '<div class="funnel-row" style="display:flex;align-items:center;'
        + 'gap:16px;padding:10px 0;">'
        + '<div style="min-width:210px;">'
        + '<div style="font-weight:700;color:' + WARNA["ink"]
        + ';font-size:0.92rem;">' + _esc(label) + '</div>'
        + '<div style="color:' + WARNA["muted"] + ';font-size:0.76rem;">'
        + _esc(sublabel) + '</div>'
        + '</div>'
        + '<div style="flex:1;">' + bar_html + '</div>'
        + '</div>'
    )



def wa_url(phone):
    """Build a wa.me link URL from an Indonesian phone number (spec 3.6).

    Format: https://wa.me/62{number without leading zero}. Returns an empty
    string for a missing or unusable number. Generic: any page that shows a
    contact action can use it. Used by the Beranda queue and drill-down.
    """
    if phone is None:
        return ""
    s = str(phone).strip()
    # Keep digits only. Spreadsheets sometimes carry stray spaces or symbols.
    s = "".join(ch for ch in s if ch.isdigit())
    if s == "":
        return ""
    if s.startswith("0"):
        s = s[1:]
    if s.startswith("62"):
        # Already in country-code form. Use as is.
        return "https://wa.me/" + s
    return "https://wa.me/62" + s
