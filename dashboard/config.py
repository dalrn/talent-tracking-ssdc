# config.py
# All magic numbers, paths, thresholds, weights, and palette.
# Section 5.2 of the specification.
# ANCHOR and SYNC_REF are NOT here. They are computed by the loader (Section 2.3).

# Path to the raw CSV folder, relative to the dashboard/ folder.
# dashboard/ sits beside Data/, so Data/Raw is one level up.
DATA_DIR = "../Data/Raw"

# The six CSV file names. The default tracking_company file is used.
# The three tracking_company files are byte identical (checksum verified at setup).
FILES = {
    "company": "company.csv",
    "talent_request": "talent_request.csv",
    "student_all": "student_all.csv",
    "status_student": "status_student.csv",
    "tracking_company": "tracking_company.csv",
    "tracking_student": "tracking_student.csv",
}

# The three tracking_company versions. Checksums must match at setup.
# We do not edit the CSV. The 48 broken list_nim rows are fixed in code (clean.py).
TRACKING_COMPANY_VARIANTS = [
    "tracking_company.csv",
    "tracking_company_new.csv",
    "tracking_company_old.csv",
]

# FU and Ghosting thresholds in days. Organizer rule, from send_date age.
FU_THRESHOLDS = {"FU1": 7, "FU2": 14, "FU3": 21, "GHOSTING": 28}

# Wilson confidence interval z value (95 percent).
WILSON_Z = 1.96

# Minimum sample size for the company ranking gate.
MIN_N_RANKING = 30

# Default weights for the Matching score. Sliders can change these.
BOBOT_DEFAULT = {"prodi": 35, "tools": 30, "ipk": 20, "domisili": 15}

# Default value for the BT-08 sync freshness slider, in days.
SYNC_SLIDER_DEFAULT = 30

# Ganjil semester months. Genap is the rest.
# Ganjil = August to January. Genap = February to July.
SEMESTER_GANJIL_BULAN = [8, 9, 10, 11, 12, 1]

# Palette from the mockup.
# WARNA = {
#     "accent": "#0f5f66",
#     "crit": "#b42318", "crit_bg": "#fdeceb",
#     "warn": "#b25b06", "warn_bg": "#fbf1e6",
#     "watch": "#8a6d14", "watch_bg": "#f8f3e2",
#     "hot": "#155fa0", "hot_bg": "#eaf1f8",
#     "ok": "#256a3d", "ok_bg": "#e9f3ec",
#     "ink": "#14181a", "ink2": "#4a5157", "muted": "#828b90",
#     "line": "#d5dad6", "panel": "#ffffff", "page": "#eef0ee",
#     "bar": "#3a8088", "barlite": "#bcd6d3", "ref": "#c98a3c",
# }
