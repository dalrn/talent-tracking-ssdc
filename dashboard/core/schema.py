# core/schema.py
# Category values as constants. Anti-typo layer.
# Section 5.1 of the specification.
# All values are case sensitive and must match the data exactly.
# Loader, clean, and metrics import from here. They never write raw category strings.

# progress_student, the current stage column in tracking_student (12 values).
STAGE_SELECTING = "Selecting Student by Company"
STAGE_BRIEFING = "CDC Briefing Student"
STAGE_STUDYCASE = "Study Case"
STAGE_INTERVIEW = "Interview User"
STAGE_FINAL = "Final Interview"
STAGE_PLACEMENT = "Placement"
STAGE_FU1 = "FU 1"
STAGE_FU2 = "FU 2"
STAGE_FU3 = "FU 3"
STAGE_GHOSTING = "Ghosting"
STAGE_REJECTED = "Rejected"
STAGE_FINISH = "Finish"

# rejection, the process status column in tracking_student (7 values).
REJ_ONPROGRESS = "On Progress"
REJ_PLACEMENT = "Placement"
REJ_GHOSTING = "Ghosting"
REJ_CV = "Rejection Screening CV"
REJ_STUDYCASE = "Rejection Study Case"
REJ_INTERVIEW = "Rejection Interview User"
REJ_FINAL = "Rejection Final Interview"

# ketersediaan, the availability column in status_student (3 values).
AVAIL_AVAILABLE = "Available"
AVAIL_PLACED = "Placed"
AVAIL_INACTIVE = "Tidak Aktif"

# progress column in tracking_company. Used ONLY to detect Draft requests.
# The funnel never uses this column (Section 3.2).
TC_PROGRESS_DRAFT = "Draft"

# CV value that counts as present.
CV_ADA = "Ada"

# working_arrangement values where domisili scoring is active (Section 4.9).
WA_WFO = "WFO"
WA_HYBRID = "Hybrid"
WA_DOMISILI_ACTIVE = {WA_WFO, WA_HYBRID}

# Funnel stage order, top to bottom (Section 4.13). Team assumption, documented.
FUNNEL_ORDER = [
    STAGE_SELECTING,
    STAGE_BRIEFING,
    STAGE_STUDYCASE,
    STAGE_INTERVIEW,
    STAGE_FINAL,
    STAGE_PLACEMENT,
]

# Map from a funnel stage to the rejection category that drops out of that gate.
# CDC Briefing has no rejection category of its own, so it is absent here.
REJ_GATE_MAP = {
    STAGE_SELECTING: REJ_CV,
    STAGE_STUDYCASE: REJ_STUDYCASE,
    STAGE_INTERVIEW: REJ_INTERVIEW,
    STAGE_FINAL: REJ_FINAL,
}

# The 18 programs (closed set) grouped into 6 fallback clusters (Section 5.3).
# The cluster is used ONLY as a Matching fallback when exact candidates run short.
PRODI_CLUSTER = {
    "IT & Data": [
        "Informatika", "Sistem Informasi",
        "Pendidikan Teknik Informatika", "Statistika",
    ],
    "Bisnis & Ekonomi": [
        "Manajemen", "Akuntansi", "Ekonomi Pembangunan",
    ],
    "Teknik": [
        "Teknik Industri", "Teknik Elektro", "Teknik Mesin", "Teknik Sipil",
    ],
    "Komunikasi & Kreatif": [
        "Ilmu Komunikasi", "Desain Komunikasi Visual", "Sastra Inggris",
    ],
    "Sosial & Humaniora": [
        "Psikologi", "Ilmu Hukum",
    ],
    "Sains & Life": [
        "Farmasi", "Agroteknologi",
    ],
}

# Reverse lookup: program name to its cluster name.
PRODI_TO_CLUSTER = {
    prodi: cluster
    for cluster, prodi_list in PRODI_CLUSTER.items()
    for prodi in prodi_list
}
