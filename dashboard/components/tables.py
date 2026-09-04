# components/tables.py
# Owner: shared. Purpose: interactive table (st.dataframe on_select) and
# drill-down panel. See spec Section 6, used by pages/1_Beranda.py Section
# 6.1 points 3 and 4.
#
# Generic like components/html.py: no page specific content is baked in,
# any caller passes its own already-filtered dataframe. Metrics are never
# computed here beyond what core/metrics.py already exposes (idle_days,
# is_placement_success) - this module only reshapes/joins for display and
# renders the panel markup.

import pandas as pd
import streamlit as st

import config
import schema
from core import metrics
import components.html as H

WARNA = config.WARNA


def wa_url(hp):
    """Build a wa.me link from a phone number (Section 3.6). None if unusable.

    Strips a leading 0 or 62 country code before prefixing 62, per the
    documented rule: https://wa.me/62{nomor_tanpa_nol_depan}.
    """
    if hp is None or (isinstance(hp, float) and pd.isna(hp)):
        return None
    s = str(hp).strip()
    if s == "" or s.lower() == "nan":
        return None
    if s.startswith("0"):
        s = s[1:]
    elif s.startswith("62"):
        s = s[2:]
    return "https://wa.me/62" + s


# ---------------------------------------------------------------------------
# Queue table builders (Section 6.1 point 3). Two shapes: stage-based
# segments (Ghosting/FU/Interview) and the Eligible segment, which the spec
# says uses a different column shape (no tahap/diam, program/IPK/domisili
# and a CV badge instead).
# ---------------------------------------------------------------------------

def build_stage_queue(subset, student_all, anchor):
    """Build the display dataframe for a stage-based queue segment.

    subset: tracking_student rows already filtered to the active segment's
    stage(s) by the caller. Adds Diam (idle_days, Section 4.7) and Kontak
    (student_all.hp, Section 3.6 - the recommended contact source over the
    broken status_student.no_whatsapp). NIM is kept as a hidden helper
    column so the caller can look up the selected row after display.
    Source columns: NIM, student_name, company, position, progress_student,
    last_update, student_all.hp.
    """
    df = subset.copy()
    df["Diam (hari)"] = metrics.idle_days(df, anchor)
    hp_lookup = student_all.set_index("NIM")["hp"]
    df["Kontak"] = df["NIM"].map(hp_lookup).map(wa_url)
    df["Mahasiswa"] = df["student_name"] + " (" + df["NIM"] + ")"
    df["Perusahaan & Posisi"] = df["company"] + " - " + df["position"]
    df["Tahap"] = df["progress_student"]
    return df[
        ["NIM", "Mahasiswa", "Perusahaan & Posisi", "Tahap", "Diam (hari)", "Kontak"]
    ]


def build_eligible_queue(subset, student_all):
    """Build the display dataframe for the Eligible, belum dikirim segment.

    Different column shape than the stage-based segments (Section 6.1 point
    2): program/IPK/domisili plus a CV badge, no tahap/diam since these
    students have no tracking_student row yet.
    Source columns: NIM, nama, program_studi, IPK, domisili, CV,
    student_all.hp.
    """
    df = subset.copy()
    hp_lookup = student_all.set_index("NIM")["hp"]
    df["Kontak"] = df["NIM"].map(hp_lookup).map(wa_url)
    df["Mahasiswa"] = df["nama"] + " (" + df["NIM"] + ")"
    df["CV"] = df["CV"].map(lambda v: "Ada" if v == schema.CV_ADA else "Tanpa CV")
    return df.rename(columns={"program_studi": "Prodi", "domisili": "Domisili"})[
        ["NIM", "Mahasiswa", "Prodi", "IPK", "Domisili", "CV", "Kontak"]
    ]


# ---------------------------------------------------------------------------
# Drill-down panel (Section 6.1 point 4). The team's stated differentiator:
# profile plus every process this student has anywhere, plus an automatic
# callout when the student is already placed elsewhere.
# ---------------------------------------------------------------------------

def render_drilldown_panel(nim, status_student, tracking_student, student_all):
    """Render the profile + cross-company process panel for one NIM.

    Looks up the student in status_student (prodi, IPK, domisili, CV,
    portofolio, tools), then every tracking_student row for that NIM
    regardless of which company, and flags with a callout if any of those
    rows already has rejection == Placement (Section 4.1a) elsewhere - the
    1,325 placed-and-still-ghosting case the spec calls out by name.
    Source columns: status_student.* by NIM, tracking_student.* by NIM,
    student_all.hp.
    """
    prof_rows = status_student[status_student["NIM"] == nim]
    if prof_rows.empty:
        st.info("Profil mahasiswa tidak ditemukan.")
        return
    prof = prof_rows.iloc[0]

    hp = student_all.set_index("NIM")["hp"].get(nim)
    wa = wa_url(hp)

    # Frozen header: name, then IPK/domisili/CV as plain text underneath -
    # not kpi_card, kept simple on purpose. This part sits outside the
    # scrollable container below, so it stays in view while the track list
    # scrolls (the closest plain-Streamlit equivalent of a frozen header,
    # since st.container has no partial-freeze of its own content).
    cv_ok = prof["CV"] == schema.CV_ADA
    cv_badge = H.badge("CV ada", "ok") if cv_ok else H.badge("Tanpa CV", "warn")
    portofolio = H._esc(prof.get("portofolio", "-")) or "-"

    st.markdown("#### " + H._esc(prof["nama"]))
    st.caption(
        "NIM " + str(nim) + " · " + H._esc(prof["program_studi"])
        + " · semester " + str(prof["semester"])
    )
    st.markdown(
        '<div style="font-size:0.85rem;color:' + WARNA["ink"] + ';line-height:1.7;">'
        + '<b>IPK</b> ' + H._esc(prof["IPK"]) + ' &nbsp;·&nbsp; '
        + '<b>Domisili</b> ' + H._esc(prof["domisili"]) + ' &nbsp;·&nbsp; '
        + cv_badge
        + '<br><span style="color:' + WARNA["ink2"] + ';font-size:0.78rem;">'
        + 'Portofolio: ' + portofolio + '</span></div>',
        unsafe_allow_html=True,
    )

    tools_raw = prof.get("tools", "")
    tools_list = [t.strip() for t in str(tools_raw).split(",") if t.strip()]
    if tools_list:
        st.markdown(
            "**Tools:** " + ", ".join(H._esc(t) for t in tools_list)
        )

    st.markdown("---")

    # Scrollable track: everything about this student's process history.
    # Fixed height on purpose so it scrolls independently of the frozen
    # header above, instead of growing the whole panel.
    with st.container(height=340):
        st.markdown("**Semua proses mahasiswa ini di seluruh perusahaan**")

        all_proc = tracking_student[tracking_student["NIM"] == nim]
        if all_proc.empty:
            st.caption("Belum pernah dikirim ke perusahaan manapun.")
        else:
            placement_mask = metrics.is_placement_success(all_proc)
            if placement_mask.any():
                placed_company = all_proc.loc[placement_mask, "company"].iloc[0]
                st.markdown(
                    H.callout(
                        "Sudah placed di " + str(placed_company) + ". Konfirmasi "
                        "dulu sebelum follow up.",
                        kind="crit", title="Sudah ditempatkan di tempat lain",
                    ),
                    unsafe_allow_html=True,
                )

            columns = ["Perusahaan", "Posisi", "Tahap", "Rejection"]
            align = ["left", "left", "left", "left"]
            rows = []
            for _, r in all_proc.sort_values("last_update", ascending=False).iterrows():
                rows.append(
                    [r["company"], r["position"], r["progress_student"], r["rejection"]]
                )
            st.markdown(H.read_only_table(columns, rows, align=align), unsafe_allow_html=True)

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    b1, b2 = st.columns(2)
    with b1:
        if wa:
            st.link_button("Hubungi via WhatsApp", wa, use_container_width=True)
        else:
            st.button(
                "Hubungi via WhatsApp", disabled=True, use_container_width=True,
                help="Nomor tidak tersedia",
            )
    with b2:
        ditindak = st.session_state.setdefault("ditindak_nims", set())
        if nim in ditindak:
            st.button(
                "Sudah ditandai ditindak", disabled=True, use_container_width=True,
            )
        else:
            if st.button("Tandai ditindak", key="tandai_" + str(nim), use_container_width=True):
                ditindak.add(nim)
    st.caption("Status 'ditindak' hanya tersimpan selama sesi ini (session_state), tidak permanen.")
