# core/cached.py
# Cached wrappers around the expensive core/metrics.py functions.
#
# Why this module exists
# ----------------------
# Streamlit reruns a page script top to bottom on every widget interaction:
# a button click, a slider drag, a radio switch, a table row selection. The
# metrics below are recomputed identically on each of those reruns even when
# nothing about the data or the filters changed. Measured on the full data,
# company_league alone cost about 4 s per rerun before this.
#
# Cache key policy (agreed with the owner): cache PER FILTER RANGE.
# Each wrapper takes a filter_key, a small hashable tuple describing which
# slice of the data the caller already applied, plus the sliced dataframes
# themselves as underscore-prefixed (unhashed) arguments. Streamlit hashes
# only filter_key, so a repeat interaction under the same filters is a cache
# hit, and changing the sidebar date range or jenis_penempatan computes once
# for the new range and then hits again.
#
# The wrappers never redefine a metric. Each one calls straight through to
# core/metrics.py, which stays the single source of every definition.

import streamlit as st

import config
from core import metrics


def filter_key(periode_filter=None, jenis_penempatan=None, extra=None):
    """Build the hashable cache key describing the current filter slice.

    periode_filter is the (start, end) Timestamp pair from the shared sidebar,
    or None for the full range. jenis_penempatan is the Monitoring page filter
    ("Semua" or a value). extra carries any page-specific scalar that changes
    the result. Timestamps are reduced to ISO strings so the key stays cheap
    and stable to hash.
    """
    if periode_filter:
        start, end = periode_filter
        periode = (str(start), str(end))
    else:
        periode = None
    return (periode, jenis_penempatan, extra)


# ---------------------------------------------------------------------------
# Per company aggregates. The heaviest group before the vectorisation pass,
# and still the most worth caching because several pages ask for them.
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def company_league(_ts, filter_key, min_n=config.MIN_N_RANKING):
    return metrics.company_league(_ts, min_n=min_n)


@st.cache_data(show_spinner=False)
def company_league_gate_count(_ts, filter_key, min_n=config.MIN_N_RANKING):
    return metrics.company_league_gate_count(_ts, min_n=min_n)


@st.cache_data(show_spinner=False)
def ghosting_rate_per_company(_ts, filter_key, min_n=config.MIN_N_RANKING):
    return metrics.ghosting_rate_per_company(_ts, min_n=min_n)


@st.cache_data(show_spinner=False)
def ghosting_rate_per_company_murni(_ts, filter_key, min_n=config.MIN_N_RANKING):
    return metrics.ghosting_rate_per_company_murni(_ts, min_n=min_n)


@st.cache_data(show_spinner=False)
def max_ghosting_case_company(_ts, filter_key, min_n=config.MIN_N_RANKING):
    return metrics.max_ghosting_case_company(_ts, min_n=min_n)


@st.cache_data(show_spinner=False)
def response_time_per_company(_ts, _tc, anchor, filter_key,
                              min_n=config.MIN_N_RANKING):
    return metrics.response_time_per_company(_ts, _tc, anchor, min_n=min_n)


# ---------------------------------------------------------------------------
# Ghosting classification. Row level, feeds both the Monitoring tables and
# the murni variant above.
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def klasifikasi_ghosting_reporting(_ts, filter_key):
    return metrics.klasifikasi_ghosting(
        _ts, ghosting_mask=metrics.ghosting_reporting_mask(_ts)
    )


# ---------------------------------------------------------------------------
# Beranda queue and segment counts. Rebuilt on every segment button click and
# every keystroke in the search box before this.
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def beranda_queue(_ts, anchor, filter_key):
    return metrics.beranda_queue(_ts, anchor)


@st.cache_data(show_spinner=False)
def beranda_segment_counts(_ts, _ss, filter_key):
    return metrics.beranda_segment_counts(_ts, _ss)


@st.cache_data(show_spinner=False)
def eligible_belum_dikirim(_ss, _ts, filter_key):
    return metrics.eligible_belum_dikirim(_ss, _ts)


# ---------------------------------------------------------------------------
# Analitik trends and segments.
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def trend_per_period(_ts, _tc, mode, filter_key):
    return metrics.trend_per_period(_ts, _tc, mode=mode)


@st.cache_data(show_spinner=False)
def segment_program(_ts, _ss, filter_key):
    return metrics.segment_program(_ts, _ss)


@st.cache_data(show_spinner=False)
def segment_sector(_ts, _tc, _co, filter_key):
    return metrics.segment_sector(_ts, _tc, _co)


@st.cache_data(show_spinner=False)
def drift_student_all_vs_status(_sa, _ss, filter_key):
    return metrics.drift_student_all_vs_status(_sa, _ss)


@st.cache_data(show_spinner=False)
def placed_diluar_cakupan(_ss, _ts, filter_key):
    return metrics.placed_diluar_cakupan(_ss, _ts)


@st.cache_data(show_spinner=False)
def placed_belum_update_status(_ss, _ts, filter_key):
    return metrics.placed_belum_update_status(_ss, _ts)


# ---------------------------------------------------------------------------
# Descriptive lookup for the Monitoring company rows. Not a metric: it is the
# most common jenis_penempatan per company, used only as a row subtitle.
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def jenis_penempatan_lookup(_ts, filter_key):
    """Most common jenis_penempatan per company, as a Series indexed by company.

    Same result as groupby("company")["jenis_penempatan"].agg(mode-first) but
    computed with one grouped value_counts instead of calling Series.mode()
    twice per company. mode() returns its values sorted, so the winner is the
    first value among those tied on the highest count; sorting by count
    descending then by value ascending and keeping the first row per company
    reproduces that exact choice.
    """
    counts = (
        _ts.groupby(["company", "jenis_penempatan"], dropna=True)
        .size()
        .reset_index(name="_n")
    )
    if counts.empty:
        return counts.set_index("company")["jenis_penempatan"] if len(counts.columns) else counts
    counts = counts.sort_values(
        ["company", "_n", "jenis_penempatan"], ascending=[True, False, True]
    )
    winner = counts.drop_duplicates(subset="company", keep="first")
    return winner.set_index("company")["jenis_penempatan"]
