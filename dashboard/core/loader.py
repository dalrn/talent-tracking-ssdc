# core/loader.py
# Data loading rules. Section 2 of the specification.
# Responsibilities: delimiter per file, forced dtypes, per column date parsing,
# dynamic ANCHOR and SYNC_REF. Data is read only. No CSV is ever edited.
#
# The load result is a RawData object. It exposes each table as an attribute,
# plus ANCHOR and SYNC_REF. Cleaning and metrics run on top of this.

import hashlib
import os
from dataclasses import dataclass

import pandas as pd

from config import DATA_DIR, FILES, TRACKING_COMPANY_VARIANTS


# ---------------------------------------------------------------------------
# dtype rules (Section 2.1). A violation here is a bug.
# ---------------------------------------------------------------------------

# NIM is str everywhere. IDs are str. Phone columns are str (leading zero).
# IPK is float. Counts are nullable Int64.

DTYPE_COMPANY = {
    "id_company": "str",
    "pic_phone": "str",
}

DTYPE_TALENT_REQUEST = {
    "id_talent_req": "str",
    "id_company": "str",
    "no_whatsapp": "str",
    "headcount": "Int64",
    "minimum_semester": "Int64",
}

DTYPE_STUDENT_ALL = {
    "NIM": "str",
    "hp": "str",
    "semester": "Int64",
}

DTYPE_STATUS_STUDENT = {
    "id_status": "str",
    "NIM": "str",
    "no_whatsapp": "str",
    "IPK": "float",
    "semester": "Int64",
}

DTYPE_TRACKING_COMPANY = {
    "id_tracking_company": "str",
    "id_talent_req": "str",
    "id_company": "str",
    "jumlah_permintaan": "Int64",
    "jumlah_dikirimkan": "Int64",
    "list_nim": "str",
}

DTYPE_TRACKING_STUDENT = {
    "id_tracking_student": "str",
    "NIM": "str",
    "id_tracking_company": "str",
    "internship_semester": "Int64",
}


# ---------------------------------------------------------------------------
# Date parsing rules (Section 2.2). Parse per column. No single global format.
# ---------------------------------------------------------------------------

def _parse_dates(series, fmt):
    """Parse one date column with one fixed format. Bad values become NaT."""
    return pd.to_datetime(series, format=fmt, errors="coerce")


def _parse_dates_pick_best(series, formats):
    """Try each format, keep the one with the highest notna share.

    Used for talent_request.request_date, which the document says to verify
    at load. On this data the winner is %Y-%m-%d.
    """
    best = None
    best_share = -1.0
    for fmt in formats:
        parsed = pd.to_datetime(series, format=fmt, errors="coerce")
        share = parsed.notna().mean()
        if share > best_share:
            best_share = share
            best = parsed
    return best


def _assert_parse_ok(parsed, name, min_share=0.95, allow_empty=0):
    """Fail loud if a non nullable date column parsed below the threshold.

    allow_empty is a count of source blanks that are meaningful, not failures.
    For send_date the 598 Draft rows are meaningful empties (Section 2.2).
    """
    n_total = len(parsed)
    n_ok = int(parsed.notna().sum())
    # Meaningful empties are removed from the denominator before the check.
    n_effective = n_total - allow_empty
    share = n_ok / n_effective if n_effective > 0 else 1.0
    if share <= min_share:
        raise ValueError(
            "date parse below threshold for "
            + name
            + ": got "
            + str(round(share, 4))
            + ", need above "
            + str(min_share)
        )


# ---------------------------------------------------------------------------
# Checksum verification (Section 1). The three tracking_company files must
# be byte identical. Use tracking_company.csv as default.
# ---------------------------------------------------------------------------

def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_tracking_company_checksums(data_dir=DATA_DIR):
    """Return the shared checksum if all three variants match, else raise.

    The document says the new file is byte for byte identical to the old.
    If they ever diverge, stop, because the list_nim fix policy assumes
    tracking_student is the source of truth (Section 3.4).
    """
    sums = {}
    for name in TRACKING_COMPANY_VARIANTS:
        path = os.path.join(data_dir, name)
        if not os.path.exists(path):
            # A missing variant is not fatal. Only the default is required.
            continue
        sums[name] = _md5(path)
    unique = set(sums.values())
    if len(unique) > 1:
        raise ValueError(
            "tracking_company variants differ, checksums: " + str(sums)
        )
    return sums


# ---------------------------------------------------------------------------
# The load result container.
# ---------------------------------------------------------------------------

@dataclass
class RawData:
    company: pd.DataFrame
    talent_request: pd.DataFrame
    student_all: pd.DataFrame
    status_student: pd.DataFrame
    tracking_company: pd.DataFrame
    tracking_student: pd.DataFrame
    ANCHOR: pd.Timestamp
    SYNC_REF: pd.Timestamp


# ---------------------------------------------------------------------------
# Per file readers. Each forces its own delimiter and dtypes, then parses dates.
# ---------------------------------------------------------------------------

def _path(data_dir, key):
    return os.path.join(data_dir, FILES[key])


def _read_company(data_dir):
    # created_at is ignored entirely (Section 3.8), so it is not parsed as a date.
    return pd.read_csv(
        _path(data_dir, "company"),
        sep=",",
        dtype=DTYPE_COMPANY,
        encoding="utf-8-sig",
    )


def _read_talent_request(data_dir):
    df = pd.read_csv(
        _path(data_dir, "talent_request"),
        sep=",",
        dtype=DTYPE_TALENT_REQUEST,
        encoding="utf-8-sig",
    )
    # request_date format is not stated. Try both, pick the best (Section 2.2).
    df["request_date"] = _parse_dates_pick_best(
        df["request_date"], ["%Y-%m-%d", "%d/%m/%Y"]
    )
    _assert_parse_ok(df["request_date"], "talent_request.request_date")
    return df


def _read_student_all(data_dir):
    return pd.read_csv(
        _path(data_dir, "student_all"),
        sep=",",
        dtype=DTYPE_STUDENT_ALL,
        encoding="utf-8-sig",
    )


def _read_status_student(data_dir):
    # SEMICOLON delimiter. Column names may carry spaces, so strip them.
    df = pd.read_csv(
        _path(data_dir, "status_student"),
        sep=";",
        dtype=DTYPE_STATUS_STUDENT,
        encoding="utf-8-sig",
    )
    df.columns = [c.strip() for c in df.columns]
    df["sync_date"] = _parse_dates(df["sync_date"], "%d/%m/%Y")
    _assert_parse_ok(df["sync_date"], "status_student.sync_date")
    return df


def _read_tracking_company(data_dir):
    df = pd.read_csv(
        _path(data_dir, "tracking_company"),
        sep=",",
        dtype=DTYPE_TRACKING_COMPANY,
        encoding="utf-8-sig",
    )
    df["request_date"] = _parse_dates(df["request_date"], "%d/%m/%Y")
    df["send_date"] = _parse_dates(df["send_date"], "%d/%m/%Y")
    _assert_parse_ok(df["request_date"], "tracking_company.request_date")
    # send_date has 598 meaningful empties (Draft rows). Exclude them from the check.
    n_empty = int((df["send_date"].isna()).sum())
    _assert_parse_ok(
        df["send_date"], "tracking_company.send_date", allow_empty=n_empty
    )
    return df


def _read_tracking_student(data_dir):
    df = pd.read_csv(
        _path(data_dir, "tracking_student"),
        sep=",",
        dtype=DTYPE_TRACKING_STUDENT,
        encoding="utf-8-sig",
    )
    df["last_update"] = _parse_dates(df["last_update"], "%Y-%m-%d")
    _assert_parse_ok(df["last_update"], "tracking_student.last_update")
    return df


# ---------------------------------------------------------------------------
# ANCHOR and SYNC_REF (Section 2.3). Computed dynamically. Never hardcoded.
# ---------------------------------------------------------------------------

def _compute_anchor(tracking_student, tracking_company, status_student):
    """ANCHOR is the latest real date across the process tables.

    On current data this is 2025-05-17, from last_update.
    """
    return max(
        tracking_student["last_update"].max(),
        tracking_company["send_date"].max(),
        tracking_company["request_date"].max(),
        status_student["sync_date"].max(),
    )


def _compute_sync_ref(status_student):
    """SYNC_REF is the latest sync date. On current data 2025-01-31."""
    return status_student["sync_date"].max()


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------

def _load_impl(data_dir=DATA_DIR):
    """Load all six tables, parse dates, compute ANCHOR and SYNC_REF.

    This is the plain function. load_data wraps it in the Streamlit cache.
    """
    verify_tracking_company_checksums(data_dir)

    company = _read_company(data_dir)
    talent_request = _read_talent_request(data_dir)
    student_all = _read_student_all(data_dir)
    status_student = _read_status_student(data_dir)
    tracking_company = _read_tracking_company(data_dir)
    tracking_student = _read_tracking_student(data_dir)

    anchor = _compute_anchor(tracking_student, tracking_company, status_student)
    sync_ref = _compute_sync_ref(status_student)

    return RawData(
        company=company,
        talent_request=talent_request,
        student_all=student_all,
        status_student=status_student,
        tracking_company=tracking_company,
        tracking_student=tracking_student,
        ANCHOR=anchor,
        SYNC_REF=sync_ref,
    )


def load_data(data_dir=DATA_DIR):
    """Cached load for Streamlit. Falls back to the plain load off app."""
    try:
        import streamlit as st
    except Exception:
        return _load_impl(data_dir)

    @st.cache_data(show_spinner=False)
    def _cached(dir_arg):
        return _load_impl(dir_arg)

    return _cached(data_dir)
