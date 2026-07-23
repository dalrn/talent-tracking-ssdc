# core/metrics.py
# Metric dictionary. Section 4 of the specification. Core of the project.
# Every metric is defined ONLY here. Pages call these functions. Pages never
# rewrite a formula. Category values come from schema.py, never raw strings.
#
# Each function takes cleaned dataframes (from clean.py) and returns a value,
# a boolean mask, or a dataframe. Each has a short docstring with its
# definition and source columns.

import pandas as pd

import config
import schema


# ---------------------------------------------------------------------------
# 3.1 helper. The clean base used by every success rate.
# ---------------------------------------------------------------------------

def ts_bersih(tracking_student):
    """tracking_student without anomaly rows (Section 3.1).

    Base for all success rate numerators and denominators.
    Source column: is_anomali (added in clean.py).
    """
    return tracking_student[~tracking_student["is_anomali"]]


# ---------------------------------------------------------------------------
# 4.1 Placement. Two definitions for two contexts.
# ---------------------------------------------------------------------------

def is_placement_success(tracking_student):
    """Success definition mask: rejection == Placement (Section 4.1a).

    This is the BT-04 success definition, used for all success rates.
    On full data this is 8,955 rows, 5,759 unique NIM.
    Source column: rejection.
    """
    return tracking_student["rejection"] == schema.REJ_PLACEMENT


def is_stage_placement(tracking_student):
    """Operational stage mask: progress_student == Placement (Section 4.1b).

    Used only to show processes whose current stage is Placement.
    On full data this is 7,534 rows.
    Source column: progress_student.
    """
    return tracking_student["progress_student"] == schema.STAGE_PLACEMENT


# ---------------------------------------------------------------------------
# 4.2 BT-04 success rate. Recompute from data. Clean base, rejection numerator.
# ---------------------------------------------------------------------------

def success_rate_per_shipment(tracking_student):
    """Conversion per process (Section 4.2a).

    Placements over shipments, both on the anomaly free base.
    = placements / len(ts_bersih). About 22.9 percent on full data.
    Source columns: rejection, is_anomali.
    """
    base = ts_bersih(tracking_student)
    n = len(base)
    if n == 0:
        return 0.0
    k = int((base["rejection"] == schema.REJ_PLACEMENT).sum())
    return k / n


def success_denominator_per_student(tracking_student):
    """Unique NIM ever sent, on the anomaly free base (Section 4.2b).

    Computed, not hardcoded. Students whose entire row set is anomalous
    drop out. At most 10,174.
    Source columns: NIM, is_anomali.
    """
    base = ts_bersih(tracking_student)
    return int(base["NIM"].nunique())


def success_numerator_per_student(tracking_student):
    """Unique NIM with a placement, on the anomaly free base (Section 4.2b).

    On full data this is 5,759.
    Source columns: NIM, rejection, is_anomali.
    """
    base = ts_bersih(tracking_student)
    return int(base.loc[base["rejection"] == schema.REJ_PLACEMENT, "NIM"].nunique())


def success_rate_per_student(tracking_student):
    """Success per person (Section 4.2b).

    Unique placed NIM over unique sent NIM, both on the clean base.
    Source columns: NIM, rejection, is_anomali.
    """
    denom = success_denominator_per_student(tracking_student)
    if denom == 0:
        return 0.0
    return success_numerator_per_student(tracking_student) / denom


# ---------------------------------------------------------------------------
# 4.3 Eligible (BT-06).
# ---------------------------------------------------------------------------

def is_eligible(status_student):
    """Eligible mask: ketersediaan == Available (Section 4.3).

    Organizer confirmed eligible equals the ketersediaan column.
    On full data 7,135 students.
    Source column: ketersediaan.
    """
    return status_student["ketersediaan"] == schema.AVAIL_AVAILABLE


def eligible_tanpa_cv(status_student):
    """Eligible students who have no CV (Section 4.3).

    They stay eligible, but get a "tanpa CV" badge. On full data 1,448.
    Source columns: ketersediaan, CV.
    """
    mask = is_eligible(status_student) & (status_student["CV"] != schema.CV_ADA)
    return status_student[mask]


# ---------------------------------------------------------------------------
# 4.4 Eligible, not yet sent (Beranda). Recompute. No CV filter.
# ---------------------------------------------------------------------------

def eligible_belum_dikirim(status_student, tracking_student):
    """Available students who never appear in tracking_student (Section 4.4).

    No CV filter, unlike the old mockup. The "tanpa CV" badge is per row.
    Count is computed, not hardcoded.
    Source columns: ketersediaan, NIM, tracking_student.NIM.
    """
    sent_nims = set(tracking_student["NIM"].dropna())
    mask = is_eligible(status_student) & (~status_student["NIM"].isin(sent_nims))
    return status_student[mask]


# ---------------------------------------------------------------------------
# 4.5 FU and Ghosting. Use the existing labels in the data. Do not recompute.
# ---------------------------------------------------------------------------

def ghosting_operasional_mask(tracking_student):
    """Operational ghosting: progress_student == Ghosting (Section 4.5).

    Beranda queue view. On full data 2,905 rows.
    Source column: progress_student.
    """
    return tracking_student["progress_student"] == schema.STAGE_GHOSTING


def ghosting_reporting_mask(tracking_student):
    """Reporting ghosting: rejection == Ghosting (Section 4.5).

    Monitoring aggregate, includes archived to Finish. On full data 3,421.
    Source column: rejection.
    """
    return tracking_student["rejection"] == schema.REJ_GHOSTING


# ---------------------------------------------------------------------------
# 4.6 Three ghosting types. Team inference via last_update order.
# ---------------------------------------------------------------------------

def klasifikasi_ghosting(tracking_student, ghosting_mask=None):
    """Classify each ghosting row into a likely type (Section 4.6).

    For a ghosting row of a student, compare the earliest placement date
    (rejection == Placement, reference 4.1a) against the ghosting last_update.
    Types: murni_perusahaan, mahasiswa_mangkir, tak_tentu.
    This is inference, framed with "kemungkinan" in the UI. Numbers computed.
    Source columns: NIM, rejection, progress_student, last_update.
    Pass ghosting_mask to pick the context set (operational or reporting).
    """
    if ghosting_mask is None:
        ghosting_mask = ghosting_operasional_mask(tracking_student)

    ghost = tracking_student[ghosting_mask]

    # Earliest placement date per NIM, on the official placement definition.
    pl = tracking_student[tracking_student["rejection"] == schema.REJ_PLACEMENT]
    pl_min = pl.groupby("NIM")["last_update"].min()

    types = []
    for _, row in ghost.iterrows():
        nim = row["NIM"]
        t_ghost = row["last_update"]
        if nim not in pl_min.index:
            types.append("murni_perusahaan")
            continue
        first_pl = pl_min.loc[nim]
        if pd.isna(first_pl) or pd.isna(t_ghost):
            types.append("tak_tentu")
        elif first_pl < t_ghost:
            types.append("mahasiswa_mangkir")
        elif first_pl > t_ghost:
            types.append("murni_perusahaan")
        else:
            types.append("tak_tentu")

    out = ghost.copy()
    out["tipe_ghosting"] = types
    return out


# ---------------------------------------------------------------------------
# 4.7 Beranda queue urgency helper.
# ---------------------------------------------------------------------------

def idle_days(tracking_student, anchor):
    """Idle age in days: anchor minus last_update (Section 4.7).

    Used to sort within a segment, longest idle on top.
    Source column: last_update.
    """
    return (anchor - tracking_student["last_update"]).dt.days


# ---------------------------------------------------------------------------
# 4.8 BT-03 KPI (Matching).
# ---------------------------------------------------------------------------

def draft_requests(tracking_company):
    """Requests not yet served: tracking_company.progress == Draft (Section 4.8).

    On full data 598. This is the only allowed use of tracking_company.progress.
    Source column: progress.
    """
    return tracking_company[tracking_company["progress"] == schema.TC_PROGRESS_DRAFT]


def request_age_days(tracking_company, anchor):
    """Request age in days: anchor minus request_date (Section 4.8).

    Shown as "X hari sejak pengajuan" per request card.
    Source column: request_date.
    """
    return (anchor - tracking_company["request_date"]).dt.days


def orphan_talent_req(talent_request, tracking_company):
    """Count of id_talent_req with no tracking row, and the reverse (Section 4.8).

    Reported as a positive hygiene finding. On full data 0 and 0.
    Source columns: talent_request.id_talent_req, tracking_company.id_talent_req.
    """
    tr_ids = set(talent_request["id_talent_req"].dropna())
    tc_ids = set(tracking_company["id_talent_req"].dropna())
    return len(tr_ids - tc_ids), len(tc_ids - tr_ids)


# ---------------------------------------------------------------------------
# 4.9 Weighted Matching score (BT-01).
# ---------------------------------------------------------------------------

def matching_gate(status_student, minimum_semester):
    """Hard gate mask before scoring (Section 4.9).

    Keep only Available students at or above the request minimum semester.
    Filter first, then score. Never score everyone per slider move.
    Source columns: ketersediaan, semester.
    """
    avail = status_student["ketersediaan"] == schema.AVAIL_AVAILABLE
    if minimum_semester is None or pd.isna(minimum_semester):
        return avail
    sem_ok = status_student["semester"] >= minimum_semester
    return avail & sem_ok


def _skor_prodi(program_studi, prodi_list, cluster_fallback=False):
    """Prodi component, 0 to 1 (Section 4.9).

    1 if the student program is in the request list. If cluster fallback is on,
    0.5 for a same cluster match. Else 0.
    """
    if program_studi in prodi_list:
        return 1.0
    if cluster_fallback:
        want_clusters = {
            schema.PRODI_TO_CLUSTER.get(p) for p in prodi_list
        }
        if schema.PRODI_TO_CLUSTER.get(program_studi) in want_clusters:
            return 0.5
    return 0.0


def _skor_tools(tools_list, tools_dibutuhkan):
    """Tools component, 0 to 1 (Section 4.9).

    Share of request tools the student has. If no tools required, treat as 1.
    """
    if not tools_dibutuhkan:
        return 1.0
    have = set(tools_list or [])
    want = set(tools_dibutuhkan)
    return len(have & want) / len(want)


def _skor_ipk(ipk, ipk_min=None):
    """IPK component, 0 to 1 (Section 4.9).

    Normalized as min(IPK/4.0, 1). Below a stated request minimum gives 0.
    """
    if ipk is None or pd.isna(ipk):
        return 0.0
    if ipk_min is not None and not pd.isna(ipk_min) and ipk < ipk_min:
        return 0.0
    return min(ipk / 4.0, 1.0)


def _skor_domisili(domisili, kota, working_arrangement):
    """Domisili component, 0 to 1 (Section 4.9).

    1 if student domicile equals the company city. Active only when the
    working arrangement is WFO or Hybrid. Returns None when inactive so the
    caller can drop its weight.
    """
    if working_arrangement not in schema.WA_DOMISILI_ACTIVE:
        return None
    return 1.0 if (domisili is not None and domisili == kota) else 0.0


def hitung_skor_matching(
    program_studi,
    tools_list,
    ipk,
    domisili,
    prodi_list,
    tools_dibutuhkan,
    kota,
    working_arrangement,
    bobot=None,
    ipk_min=None,
    cluster_fallback=False,
):
    """Weighted match score, 0 to 100 (Section 4.9).

    Score = 100 * sum(weight_i * component_i) / sum(active weights).
    Domisili is dropped from both sums when the arrangement is WFH.
    Weights come from config.BOBOT_DEFAULT by default; sliders override.
    Returns a dict with the score and the per component breakdown.
    """
    if bobot is None:
        bobot = config.BOBOT_DEFAULT

    komponen = {
        "prodi": _skor_prodi(program_studi, prodi_list, cluster_fallback),
        "tools": _skor_tools(tools_list, tools_dibutuhkan),
        "ipk": _skor_ipk(ipk, ipk_min),
        "domisili": _skor_domisili(domisili, kota, working_arrangement),
    }

    total_bobot = 0.0
    total_nilai = 0.0
    for nama, nilai in komponen.items():
        if nilai is None:
            # Inactive component (domisili on a WFH request). Drop its weight.
            continue
        w = bobot[nama]
        total_bobot += w
        total_nilai += w * nilai

    skor = 100.0 * total_nilai / total_bobot if total_bobot > 0 else 0.0
    return {"skor": skor, "komponen": komponen, "bobot_aktif": total_bobot}


# ---------------------------------------------------------------------------
# 4.10 Discrepancies and documented assumptions. Report material.
# ---------------------------------------------------------------------------

def placed_diluar_cakupan(status_student, tracking_student):
    """Placed students with no tracking_student trace (Section 4.10).

    Interpreted as placed outside the CDC flow. A BT-04 scope limitation,
    not a BT-08 sync issue. On full data 4,163 of 9,301 Placed.
    Source columns: ketersediaan, NIM, tracking_student.NIM.
    """
    sent = set(tracking_student["NIM"].dropna())
    placed = status_student[status_student["ketersediaan"] == schema.AVAIL_PLACED]
    return placed[~placed["NIM"].isin(sent)]


def placed_belum_update_status(status_student, tracking_student):
    """NIM with a placement whose ketersediaan is not Placed (Section 4.10).

    Assumed status update lag, not verifiable. On full data 621.
    Source columns: rejection, NIM, ketersediaan.
    """
    placement_nim = set(
        tracking_student.loc[
            tracking_student["rejection"] == schema.REJ_PLACEMENT, "NIM"
        ].dropna()
    )
    placed_nim = set(
        status_student.loc[
            status_student["ketersediaan"] == schema.AVAIL_PLACED, "NIM"
        ].dropna()
    )
    return placement_nim - placed_nim


# ---------------------------------------------------------------------------
# 4.11 Wilson 95 percent confidence interval (company league).
# ---------------------------------------------------------------------------

def wilson(k, n, z=config.WILSON_Z):
    """Wilson interval for a proportion (Section 4.11).

    Returns (lo, center, hi). k = placements, n = shipments.
    """
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (center - half, center, center + half)


def company_league(tracking_student, min_n=config.MIN_N_RANKING):
    """Per company placement rate with a Wilson interval (Section 4.11).

    k and n come from the anomaly free base. n is shipments per company,
    k is placements per company. Rows with n < min_n get a small sample badge.
    Returns a dataframe with id_company key columns absent, keyed by company.
    Source columns: company, rejection, is_anomali.
    Note: the company key here is the tracking_student "company" name column.
    """
    base = ts_bersih(tracking_student)
    grp = base.groupby("company")
    n = grp.size()
    k = grp.apply(lambda g: int((g["rejection"] == schema.REJ_PLACEMENT).sum()))
    out = pd.DataFrame({"n": n, "k": k})
    lo, center, hi = [], [], []
    for _, row in out.iterrows():
        a, b, c = wilson(int(row["k"]), int(row["n"]))
        lo.append(a)
        center.append(b)
        hi.append(c)
    out["wilson_lo"] = lo
    out["wilson_center"] = center
    out["wilson_hi"] = hi
    out["ci_width"] = out["wilson_hi"] - out["wilson_lo"]
    out["lolos_gate"] = out["n"] >= min_n
    out["rate"] = out["k"] / out["n"]
    return out.reset_index()


def company_league_gate_count(tracking_student, min_n=config.MIN_N_RANKING):
    """Count of companies passing the n >= min_n gate (Section 4.11).

    Computed, not hardcoded. About 543 on full data.
    """
    league = company_league(tracking_student, min_n)
    return int(league["lolos_gate"].sum())


# ---------------------------------------------------------------------------
# 4.12 BT-08. Drift status and sync freshness.
# ---------------------------------------------------------------------------

def drift_student_all_vs_status(student_all, status_student):
    """Per column drift counts between the two student tables (Section 4.12a).

    Compares the copied columns per NIM. Verified 0 across all pairs.
    Computed live so it stays correct if data changes.

    Column mapping note: status_student.email is the campus email. In
    student_all that value lives in email_kampus (email_pribadi is a
    different address). semester, program_studi, and nama share the same
    name in both tables. The result key stays "email" for readability.
    Source columns: NIM, semester, program_studi, nama, email / email_kampus.
    Returns a dict of column name to mismatch count.
    """
    # Map each compared field to (student_all column, status_student column).
    col_map = {
        "semester": ("semester", "semester"),
        "program_studi": ("program_studi", "program_studi"),
        "nama": ("nama", "nama"),
        "email": ("email_kampus", "email"),
    }
    sa_cols = ["NIM"] + [pair[0] for pair in col_map.values()]
    ss_cols = ["NIM"] + [pair[1] for pair in col_map.values()]
    merged = student_all[sa_cols].merge(
        status_student[ss_cols],
        on="NIM",
        suffixes=("_sa", "_ss"),
    )
    hasil = {}
    for key, (sa_col, ss_col) in col_map.items():
        # When the two source columns share a name, the merge suffixed them.
        left = sa_col + "_sa" if sa_col == ss_col else sa_col
        right = ss_col + "_ss" if sa_col == ss_col else ss_col
        a = merged[left].astype("string")
        b = merged[right].astype("string")
        hasil[key] = int((a != b).sum())
    return hasil


def sync_stale_count(status_student, sync_ref, x_days=config.SYNC_SLIDER_DEFAULT):
    """Count of rows whose sync age exceeds x_days (Section 4.12b).

    Age is measured against SYNC_REF, the last synced record, not ANCHOR.
    Source column: sync_date.
    """
    age = (sync_ref - status_student["sync_date"]).dt.days
    return int((age > x_days).sum())


# ---------------------------------------------------------------------------
# 4.13 Monitoring funnel (BT-02).
# ---------------------------------------------------------------------------

def funnel_active_counts(tracking_student):
    """Active count per funnel stage (Section 4.13).

    Count of progress_student per stage, in funnel order.
    Source column: progress_student.
    Returns an ordered dict of stage to count.
    """
    counts = {}
    for stage in schema.FUNNEL_ORDER:
        counts[stage] = int((tracking_student["progress_student"] == stage).sum())
    return counts


def funnel_drop_counts(tracking_student):
    """Dropped count per gate (Section 4.13).

    Count of rejection per gate, mapped to the stage that gate belongs to.
    CDC Briefing has no drop bar.
    Source column: rejection.
    Returns a dict of stage to drop count.
    """
    drops = {}
    for stage, rej_value in schema.REJ_GATE_MAP.items():
        drops[stage] = int((tracking_student["rejection"] == rej_value).sum())
    return drops


# ---------------------------------------------------------------------------
# 4.14 Time trend (BT-07).
# ---------------------------------------------------------------------------

def academic_semester_label(ts_date):
    """Map a date to an academic semester label (Section 4.14).

    Ganjil = August to January, Genap = February to July.
    Returns a label like "Ganjil 2024/2025".
    """
    if pd.isna(ts_date):
        return None
    month = ts_date.month
    year = ts_date.year
    if month in config.SEMESTER_GANJIL_BULAN:
        # Ganjil spans Aug of year Y to Jan of year Y+1.
        # January belongs to the year that started the previous August.
        start_year = year if month >= 8 else year - 1
        return "Ganjil " + str(start_year) + "/" + str(start_year + 1)
    # Genap spans Feb to Jul of the same year. The academic year started
    # the previous August.
    start_year = year - 1
    return "Genap " + str(start_year) + "/" + str(start_year + 1)


def _semester_sort_key(label):
    """Sort key for an academic semester label. Chronological order.

    "Ganjil 2024/2025" sorts before "Genap 2024/2025". Ganjil starts August,
    Genap starts February of the next calendar year, so Ganjil comes first.
    """
    if label is None:
        return (9999, 9)
    parts = label.split(" ")
    term = parts[0]
    start_year = int(parts[1].split("/")[0])
    term_rank = 0 if term == "Ganjil" else 1
    return (start_year, term_rank)


# ---------------------------------------------------------------------------
# 4.14 trend aggregation. Pure reshape, not a definition. The rate uses the
# same clean base and rejection numerator as success_rate_per_shipment (4.2).
# ---------------------------------------------------------------------------

def trend_per_period(tracking_student, tracking_company, mode="bulan"):
    """Volume and conversion rate per period (Section 4.14).

    Process time base is send_date, joined from tracking_company via
    id_tracking_company. Rate uses the anomaly free base and the
    rejection == Placement numerator, identical to 4.2. No new definition,
    only a groupby over time.

    mode "bulan": monthly periods, label like "2024-09".
    mode "semester": academic semester, label from academic_semester_label.

    Returns a dataframe sorted in chronological order with columns:
    periode, volume, placement, rate, partial.
    The last period is marked partial = True (send data stops mid period).
    Source columns: is_anomali, rejection, tracking_company.send_date.
    """
    base = ts_bersih(tracking_student)
    merged = base.merge(
        tracking_company[["id_tracking_company", "send_date"]],
        on="id_tracking_company",
        how="left",
    )
    merged = merged.dropna(subset=["send_date"]).copy()

    if mode == "semester":
        merged["periode"] = merged["send_date"].map(academic_semester_label)
        order_keys = sorted(
            merged["periode"].dropna().unique(), key=_semester_sort_key
        )
    else:
        merged["periode"] = merged["send_date"].dt.to_period("M").astype(str)
        order_keys = sorted(merged["periode"].dropna().unique())

    merged["is_pl"] = merged["rejection"] == schema.REJ_PLACEMENT
    grp = merged.groupby("periode")
    volume = grp.size()
    placement = grp["is_pl"].sum()
    out = pd.DataFrame({"volume": volume, "placement": placement})
    out = out.reindex(order_keys)
    out["rate"] = out["placement"] / out["volume"]
    out["partial"] = False
    if len(out) > 0:
        # The final period is incomplete: send_date stops mid period.
        out.iloc[-1, out.columns.get_loc("partial")] = True
    return out.reset_index().rename(columns={"index": "periode"})


# ---------------------------------------------------------------------------
# Segmentation aggregation (Section 6.4 part 3). Pure groupby, not a
# definition. Rate uses the same clean base and rejection numerator as 4.2.
# ---------------------------------------------------------------------------

def rate_per_segment(tracking_student, segment_series, label_name="segmen"):
    """Placement rate per segment value (Section 6.4 part 3).

    segment_series is a per row label aligned to the clean base rows, for
    example program_studi joined from status_student, or industry_sector
    joined from company. Rate uses the anomaly free base and the
    rejection == Placement numerator, identical to 4.2. Groupby only.

    Returns a dataframe with columns: label_name, n, k, rate, sorted by
    rate descending. n is shipments in that segment, k is placements.
    Source columns: is_anomali, rejection, plus the caller supplied segment.
    """
    base = ts_bersih(tracking_student)
    if len(segment_series) != len(base):
        raise ValueError(
            "segment_series length must match the clean base row count"
        )
    tmp = pd.DataFrame(
        {
            "seg": segment_series.values,
            "is_pl": (base["rejection"] == schema.REJ_PLACEMENT).values,
        }
    )
    grp = tmp.groupby("seg")
    out = pd.DataFrame({"n": grp.size(), "k": grp["is_pl"].sum()})
    out["rate"] = out["k"] / out["n"]
    out = out.sort_values("rate", ascending=False).reset_index()
    return out.rename(columns={"seg": label_name})


def segment_program(tracking_student, status_student):
    """Placement rate per student program (Section 6.4 part 3).

    Joins the clean base NIM to status_student.program_studi, then groups.
    Returns the rate_per_segment dataframe keyed "program_studi".
    Source columns: NIM, status_student.program_studi, rejection, is_anomali.
    """
    base = ts_bersih(tracking_student)
    prog = base.merge(
        status_student[["NIM", "program_studi"]], on="NIM", how="left"
    )["program_studi"]
    return rate_per_segment(tracking_student, prog, "program_studi")


def segment_sector(tracking_student, tracking_company, company):
    """Placement rate per company industry sector (Section 6.4 part 3).

    Joins the clean base to tracking_company for id_company, then to company
    for industry_sector, then groups.
    Returns the rate_per_segment dataframe keyed "industry_sector".
    Source columns: id_tracking_company, id_company, company.industry_sector,
    rejection, is_anomali.
    """
    base = ts_bersih(tracking_student)
    sec = base.merge(
        tracking_company[["id_tracking_company", "id_company"]],
        on="id_tracking_company",
        how="left",
    ).merge(
        company[["id_company", "industry_sector"]], on="id_company", how="left"
    )["industry_sector"]
    return rate_per_segment(tracking_student, sec, "industry_sector")


def _semester_sort_key(label):
    """Sort key for an academic semester label. Chronological order.

    "Ganjil 2024/2025" sorts before "Genap 2024/2025". Ganjil starts August,
    Genap starts February of the next calendar year, so Ganjil comes first.
    """
    if label is None:
        return (9999, 9)
    parts = label.split(" ")
    term = parts[0]
    start_year = int(parts[1].split("/")[0])
    term_rank = 0 if term == "Ganjil" else 1
    return (start_year, term_rank)


# ---------------------------------------------------------------------------
# 4.14 trend aggregation. Pure reshape, not a definition. The rate uses the
# same clean base and rejection numerator as success_rate_per_shipment (4.2).
# ---------------------------------------------------------------------------

def trend_per_period(tracking_student, tracking_company, mode="bulan"):
    """Volume and conversion rate per period (Section 4.14).

    Process time base is send_date, joined from tracking_company via
    id_tracking_company. Rate uses the anomaly free base and the
    rejection == Placement numerator, identical to 4.2. No new definition,
    only a groupby over time.

    mode "bulan": monthly periods, label like "2024-09".
    mode "semester": academic semester, label from academic_semester_label.

    Returns a dataframe sorted in chronological order with columns:
    periode, volume, placement, rate, partial.
    The last period is marked partial = True (send data stops mid period).
    Source columns: is_anomali, rejection, tracking_company.send_date.
    """
    base = ts_bersih(tracking_student)
    merged = base.merge(
        tracking_company[["id_tracking_company", "send_date"]],
        on="id_tracking_company",
        how="left",
    )
    merged = merged.dropna(subset=["send_date"]).copy()

    if mode == "semester":
        merged["periode"] = merged["send_date"].map(academic_semester_label)
        order_keys = sorted(
            merged["periode"].dropna().unique(), key=_semester_sort_key
        )
    else:
        merged["periode"] = merged["send_date"].dt.to_period("M").astype(str)
        order_keys = sorted(merged["periode"].dropna().unique())

    merged["is_pl"] = merged["rejection"] == schema.REJ_PLACEMENT
    grp = merged.groupby("periode")
    volume = grp.size()
    placement = grp["is_pl"].sum()
    out = pd.DataFrame({"volume": volume, "placement": placement})
    out = out.reindex(order_keys)
    out["rate"] = out["placement"] / out["volume"]
    out["partial"] = False
    if len(out) > 0:
        # The final period is incomplete: send_date stops mid period.
        out.iloc[-1, out.columns.get_loc("partial")] = True
    return out.reset_index().rename(columns={"index": "periode"})


# ---------------------------------------------------------------------------
# Segmentation aggregation (Section 6.4 part 3). Pure groupby, not a
# definition. Rate uses the same clean base and rejection numerator as 4.2.
# ---------------------------------------------------------------------------

def rate_per_segment(tracking_student, segment_series, label_name="segmen"):
    """Placement rate per segment value (Section 6.4 part 3).

    segment_series is a per row label aligned to the clean base rows, for
    example program_studi joined from status_student, or industry_sector
    joined from company. Rate uses the anomaly free base and the
    rejection == Placement numerator, identical to 4.2. Groupby only.

    Returns a dataframe with columns: label_name, n, k, rate, sorted by
    rate descending. n is shipments in that segment, k is placements.
    Source columns: is_anomali, rejection, plus the caller supplied segment.
    """
    base = ts_bersih(tracking_student)
    if len(segment_series) != len(base):
        raise ValueError(
            "segment_series length must match the clean base row count"
        )
    tmp = pd.DataFrame(
        {
            "seg": segment_series.values,
            "is_pl": (base["rejection"] == schema.REJ_PLACEMENT).values,
        }
    )
    grp = tmp.groupby("seg")
    out = pd.DataFrame({"n": grp.size(), "k": grp["is_pl"].sum()})
    out["rate"] = out["k"] / out["n"]
    out = out.sort_values("rate", ascending=False).reset_index()
    return out.rename(columns={"seg": label_name})


def segment_program(tracking_student, status_student):
    """Placement rate per student program (Section 6.4 part 3).

    Joins the clean base NIM to status_student.program_studi, then groups.
    Returns the rate_per_segment dataframe keyed "program_studi".
    Source columns: NIM, status_student.program_studi, rejection, is_anomali.
    """
    base = ts_bersih(tracking_student)
    prog = base.merge(
        status_student[["NIM", "program_studi"]], on="NIM", how="left"
    )["program_studi"]
    return rate_per_segment(tracking_student, prog, "program_studi")


def segment_sector(tracking_student, tracking_company, company):
    """Placement rate per company industry sector (Section 6.4 part 3).

    Joins the clean base to tracking_company for id_company, then to company
    for industry_sector, then groups.
    Returns the rate_per_segment dataframe keyed "industry_sector".
    Source columns: id_tracking_company, id_company, company.industry_sector,
    rejection, is_anomali.
    """
    base = ts_bersih(tracking_student)
    sec = base.merge(
        tracking_company[["id_tracking_company", "id_company"]],
        on="id_tracking_company",
        how="left",
    ).merge(
        company[["id_company", "industry_sector"]], on="id_company", how="left"
    )["industry_sector"]
    return rate_per_segment(tracking_student, sec, "industry_sector")

# ---------------------------------------------------------------------------
# 4.15 Ghosting rate per company. New metric for Monitoring tab Perusahaan.
# Mirrors company_league() (Section 4.11) but numerator is ghosting, not
# placement. Two variants: all reported ghosting, and murni_perusahaan only
# (from klasifikasi_ghosting). Both use n = shipments per company on the
# anomaly free base, same denominator convention as company_league.
# ---------------------------------------------------------------------------

def ghosting_rate_per_company(tracking_student, min_n=config.MIN_N_RANKING):
    """Per company ghosting rate, all reported ghosting (Section 4.15a).

    n = shipments per company, on the anomaly free base. k = ghosting rows
    per company, using the reporting definition (rejection == Ghosting).
    Rows with n < min_n get lolos_gate False, same convention as
    company_league.
    Source columns: company, rejection, is_anomali.
    """
    base = ts_bersih(tracking_student)
    grp = base.groupby("company")
    n = grp.size()
    k = grp.apply(lambda g: int((g["rejection"] == schema.REJ_GHOSTING).sum()))
    out = pd.DataFrame({"n": n, "k": k})
    out["rate"] = out["k"] / out["n"]
    out["lolos_gate"] = out["n"] >= min_n
    return out.reset_index()


def ghosting_rate_per_company_murni(tracking_student, min_n=config.MIN_N_RANKING):
    """Per company ghosting rate, murni_perusahaan cases only (Section 4.15b).

    Same n (shipments per company on the anomaly free base) as the all
    ghosting variant, so the two rates are directly comparable side by side.
    k = rows classified murni_perusahaan by klasifikasi_ghosting(), using
    the reporting mask as the ghosting context (aggregate view, not the
    operational queue).
    Source columns: company, rejection, is_anomali, last_update, NIM
    (via klasifikasi_ghosting).
    """
    base = ts_bersih(tracking_student)
    n = base.groupby("company").size()

    klas = klasifikasi_ghosting(tracking_student, ghosting_mask=ghosting_reporting_mask(tracking_student))
    murni = klas[klas["tipe_ghosting"] == "murni_perusahaan"]
    k = murni.groupby("company").size()

    out = pd.DataFrame({"n": n, "k": k}).fillna({"k": 0})
    out["k"] = out["k"].astype(int)
    out["rate"] = out["k"] / out["n"]
    out["lolos_gate"] = out["n"] >= min_n
    return out.reset_index()


# ---------------------------------------------------------------------------
# 4.16 Worst single offender, absolute count. Supports the "tersebar, bukan
# segelintir pelaku" claim: even the top company is a small absolute number.
# ---------------------------------------------------------------------------

def max_ghosting_case_company(tracking_student, min_n=config.MIN_N_RANKING):
    """Company with the highest absolute ghosting count (Section 4.16).

    Gated the same way as ghosting_rate_per_company, so a single company
    with tiny n cannot appear here from a fluke. Uses the all-ghosting
    variant (not murni_perusahaan only), since the claim is about total
    ghosting concentration, not attribution. Returns (company_name, k).
    Returns (None, 0) if no company passes the gate.
    Source columns: company, rejection, is_anomali.
    """
    league = ghosting_rate_per_company(tracking_student, min_n)
    gated = league[league["lolos_gate"]]
    if gated.empty:
        return None, 0
    row = gated.loc[gated["k"].idxmax()]
    return row["company"], int(row["k"])


# ---------------------------------------------------------------------------
# 4.17 Waktu-respons per perusahaan (Section 6.3 tab Perusahaan, point 3,
# OWNER-DECIDED: Afrizal). Time basis is send_date, not last_update: Section
# 4.5's FU/Ghosting escalation ladder is the project's established clock for
# "company hasn't responded yet", and that clock runs on send_date via
# tracking_company (join pattern per Section 4.5/4.14), not on idle_days()
# (Section 4.7), which measures last_update staleness for Beranda queue
# order and mixes in CDC-side touches, not only the company side.
# ---------------------------------------------------------------------------

def response_time_per_company(tracking_student, tracking_company, anchor,
                                min_n=config.MIN_N_RANKING):
    """Average days since send_date for each company's open processes.

    "Open" = progress_student not in schema.STAGE_TERMINAL (Placement,
    Rejected, Finish already resolved; FU1/FU2/FU3/Ghosting still open and
    waiting). send_date is joined in from tracking_company via
    id_tracking_company. Grouped by company: n = open process count,
    avg_response_days = mean age among those rows. Gated like
    company_league (n >= min_n gets lolos_gate True). A company only
    appears if it has at least one open row with a resolved send_date
    (Draft requests have no send_date and are dropped before the groupby),
    so there is no NaN or zero-division case to guard.
    Source columns: progress_student, company, id_tracking_company,
    tracking_company.send_date.
    """
    open_mask = ~tracking_student["progress_student"].isin(schema.STAGE_TERMINAL)
    open_df = tracking_student[open_mask].merge(
        tracking_company[["id_tracking_company", "send_date"]],
        on="id_tracking_company", how="left",
    )
    open_df = open_df.dropna(subset=["send_date"]).copy()
    open_df["response_days"] = (anchor - open_df["send_date"]).dt.days

    grp = open_df.groupby("company")["response_days"]
    out = pd.DataFrame({"n": grp.size(), "avg_response_days": grp.mean()})
    out["lolos_gate"] = out["n"] >= min_n
    return out.reset_index()