"""
matching engine dengan metode rule based
"""


import pandas as pd
import numpy as np
from core import schema
import config




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