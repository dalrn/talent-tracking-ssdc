# core/clean.py
# Data cleaning rules. Section 3 of the specification.
# General principle: flag, do not drop. Problem rows get a boolean column,
# they are never deleted, so they stay reportable as data quality findings.
# The raw CSVs are never edited. All fixes live here in code.
#
# This module takes a RawData object from loader.py and returns a CleanData
# object with the same tables plus the added flag and helper columns.

import re
from dataclasses import dataclass

import pandas as pd

import schema


@dataclass
class CleanData:
    company: pd.DataFrame
    talent_request: pd.DataFrame
    student_all: pd.DataFrame
    status_student: pd.DataFrame
    tracking_company: pd.DataFrame
    tracking_student: pd.DataFrame
    ANCHOR: pd.Timestamp
    SYNC_REF: pd.Timestamp


# ---------------------------------------------------------------------------
# 3.1 Finish + On Progress anomaly. The most important rule.
# Add is_anomali = True on these rows. Do not drop.
# ---------------------------------------------------------------------------

def flag_anomali(tracking_student):
    """Mark rows where progress is Finish but rejection is On Progress.

    These two values contradict each other. The organizer calls this noise.
    Every success rate uses tracking_student[~is_anomali].
    Source columns: progress_student, rejection.
    """
    df = tracking_student.copy()
    df["is_anomali"] = (
        (df["progress_student"] == schema.STAGE_FINISH)
        & (df["rejection"] == schema.REJ_ONPROGRESS)
    )
    return df


# ---------------------------------------------------------------------------
# 3.4 Reconstruct the 48 broken list_nim rows.
# A broken row holds one valid NIM then ",2", a number truncated by a sheet.
# tracking_student has exactly one extra child NIM missing from the list.
# Build list_nim_bersih. The raw CSV is not edited.
# ---------------------------------------------------------------------------

# A broken list_nim looks like "20211268,2": digits, comma, then a lone "2".
_BROKEN_PATTERN = re.compile(r"^\d+,2$")


def _is_broken_list_nim(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return bool(_BROKEN_PATTERN.match(str(value).strip()))


def build_list_nim_bersih(tracking_company, tracking_student):
    """Return tracking_company with a list_nim_bersih column and is_list_nim_broken flag.

    For a broken row, drop the trailing "2" fragment, then find the one child
    NIM in tracking_student (same id_tracking_company) missing from the list,
    and append it. Clean rows keep list_nim unchanged.
    Source columns: tracking_company.list_nim, tracking_student.NIM.

    Only the 48 broken rows are ever visited. Detection is a vectorised
    str.match over the whole column, and the child NIM lookup is built only
    for the ids of those broken rows, so the 11.952 clean rows cost nothing
    beyond the regex scan. The previous row-by-row iterrows() pass over all
    12.000 rows dominated the whole cleaning step.
    """
    df = tracking_company.copy()

    # Vectorised detection. na=False keeps missing list_nim out of the mask.
    broken = df["list_nim"].str.match(_BROKEN_PATTERN, na=False)
    df["is_list_nim_broken"] = broken.to_numpy()

    # Clean rows pass through untouched; only broken ones are rebuilt below.
    df["list_nim_bersih"] = df["list_nim"]

    broken_idx = df.index[broken]
    if len(broken_idx) == 0:
        return df

    # Child NIM sets, built only for the ids that actually need them.
    broken_ids = set(df.loc[broken_idx, "id_tracking_company"].dropna())
    kids_src = tracking_student[
        tracking_student["id_tracking_company"].isin(broken_ids)
    ]
    kids = (
        kids_src.groupby("id_tracking_company")["NIM"]
        .apply(lambda s: set(s.dropna()))
        .to_dict()
    )

    fixed_values = []
    for idx in broken_idx:
        raw = df.at[idx, "list_nim"]
        # Listed NIM values, minus the trailing lone "2".
        parts = [p.strip() for p in str(raw).split(",")]
        listed = set(parts[:-1])
        child_set = kids.get(df.at[idx, "id_tracking_company"], set())
        missing = child_set - listed
        # The document proves exactly one missing NIM per broken row.
        if len(missing) == 1:
            fixed_values.append(",".join(sorted(listed | missing)))
        else:
            # Should never happen on this data. Keep listed part, no guess.
            fixed_values.append(",".join(sorted(listed)))

    df.loc[broken_idx, "list_nim_bersih"] = fixed_values
    return df


# ---------------------------------------------------------------------------
# 3.6 Phone leading zeros.
# status_student.no_whatsapp lost its leading zero in all rows (starts 8xx).
# student_all.hp is still correct (starts 08xx). Recommendation: use hp.
# We keep hp as the source and also add a repaired no_whatsapp for consistency.
# ---------------------------------------------------------------------------

def fix_phone_leading_zero(status_student):
    """Add no_whatsapp_fixed: prefix a 0 when the number starts with 8.

    student_all.hp stays the recommended contact source. This repaired column
    exists so status_student is internally consistent if a page needs it.
    Source column: status_student.no_whatsapp.
    """
    df = status_student.copy()

    def _fix(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return v
        s = str(v).strip()
        if s.startswith("0"):
            return s
        if s.startswith("8"):
            return "0" + s
        return s

    df["no_whatsapp_fixed"] = df["no_whatsapp"].map(_fix)
    return df


# ---------------------------------------------------------------------------
# 3.7 Multi value study fields.
# Parse comma separated program lists into a Python list column for membership.
# talent_request.bidang_studi_dibutuhkan and tracking_company.bidang_studi_dicari.
# status_student.tools is also comma separated; parse it too for Matching.
# ---------------------------------------------------------------------------

def _split_multi(value):
    """Split a comma separated string into a stripped list. Blank gives []."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    s = str(value).strip()
    if s == "":
        return []
    return [part.strip() for part in s.split(",") if part.strip() != ""]


def parse_multi_value_fields(talent_request, tracking_company, status_student):
    """Add list columns for the multi value study and tools fields.

    talent_request gets bidang_studi_dibutuhkan_list.
    tracking_company gets bidang_studi_dicari_list.
    status_student gets tools_list.
    Source columns named above. No permanent explode is created.
    """
    tr = talent_request.copy()
    tc = tracking_company.copy()
    ss = status_student.copy()

    tr["bidang_studi_dibutuhkan_list"] = tr["bidang_studi_dibutuhkan"].map(_split_multi)
    tc["bidang_studi_dicari_list"] = tc["bidang_studi_dicari"].map(_split_multi)
    ss["tools_list"] = ss["tools"].map(_split_multi)

    return tr, tc, ss


# ---------------------------------------------------------------------------
# Public entry point. Runs every rule in order and returns CleanData.
# ---------------------------------------------------------------------------

def _clean_impl(raw):
    """Apply all cleaning rules to a RawData object. Return CleanData.

    Order: flag anomali, reconstruct list_nim, fix phones, parse multi value.
    ANCHOR and SYNC_REF pass through unchanged.

    This is the plain function. clean_data wraps it in the Streamlit cache.
    """
    tracking_student = flag_anomali(raw.tracking_student)

    tracking_company = build_list_nim_bersih(
        raw.tracking_company, tracking_student
    )

    status_student = fix_phone_leading_zero(raw.status_student)

    talent_request, tracking_company, status_student = parse_multi_value_fields(
        raw.talent_request, tracking_company, status_student
    )

    return CleanData(
        company=raw.company,
        talent_request=talent_request,
        student_all=raw.student_all,
        status_student=status_student,
        tracking_company=tracking_company,
        tracking_student=tracking_student,
        ANCHOR=raw.ANCHOR,
        SYNC_REF=raw.SYNC_REF,
    )


def clean_data(raw):
    """Cached cleaning for Streamlit. Falls back to the plain call off app.

    Streamlit reruns a whole page script on every widget interaction, so an
    uncached clean_data() re-ran the full cleaning pass on every click. The
    result is a read-only CleanData holding DataFrames shared by all four
    pages, so cache_resource is the right cache: no per-call hashing of the
    RawData argument, and one shared instance instead of a copy per caller.

    Keyed on the identity of the RawData object rather than its contents.
    loader.load_data() is itself cached and hands back the same RawData for
    the same data_dir, so that identity is stable for the life of the app and
    changes only when the loader cache is cleared and the CSVs are re-read.
    """
    try:
        import streamlit as st
    except Exception:
        return _clean_impl(raw)

    @st.cache_resource(show_spinner=False)
    def _cached(_raw, cache_key):
        # _raw is underscore-prefixed so Streamlit skips hashing it; cache_key
        # carries the identity that actually decides cache validity.
        return _clean_impl(_raw)

    return _cached(raw, id(raw))
