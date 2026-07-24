"""
core/matching.py
===================================================================

Komponen skor (masing-masing 0..1, lihat calculate_component_scores):
    tool_score                   -- kecocokan tools (eksplisit + implicit)
    program_study_score          -- kecocokan program studi
    ipk_score                     -- IPK/4.0, murni faktor peringkat
    interest_score                -- kecocokan bidang_minat mahasiswa vs industri_sektor
    location_score                -- kecocokan domisili vs lokasi kantor (WFO/Hybrid)
    placement_preference_score   -- kecocokan jenis_penempatan_diminati


Contoh pemakaian
-----------------
    from core.matching import MatchingEngine

    engine = MatchingEngine(paths={...})   # atau dataframes={...}
    engine.initialize()

    recommendation = engine.recommend(
        talent_request_id=selected_request,
        top_n=top_n,                 # None/kosong -> semua kandidat eligible
        weights=current_weights,     # {"tool_match":.., "program_study":.., ...}
    )

    explanation = engine.explain(selected_request, nim)

Pipeline (TIDAK diubah oleh refactor feature-engineering ini)
---------------------------------------------------------------
    Talent Request
        -> Load Candidate Pool
        -> Eligibility Filtering        (filter_candidates)
        -> Eligible Candidate Pool
        -> Rule-Based Matching          (match)
        -> Component Scoring            (calculate_component_scores)
        -> Final Scoring (real-time)    (calculate_final_score)
        -> Ranking
        -> Top-N Recommendation         (recommend)

Prinsip cache & performa (TIDAK diubah)
-----------------------------------------
* Preprocessing, historical dictionary, tool lexicon, dan interest
  pattern dihitung SATU KALI di `initialize()` / `precompute()`.
* Hasil `match()` (fitur mentah per kandidat) di-cache per
  `talent_request_id`. Mengubah bobot TIDAK memicu perhitungan ulang
  matching -- hanya `calculate_final_score()` yang murah yang dipanggil
  ulang.
* Bila `top_n` kosong (None), kandidat diproses per-batch (default 100
  baris mahasiswa) agar efisien untuk ribuan mahasiswa alih-alih
  membangun satu matriks fitur raksasa sekaligus.
"""

from __future__ import annotations

import difflib
import logging
import os
import re
from collections import Counter, defaultdict
from typing import Any, Optional

import numpy as np
import pandas as pd

import config
from core import schema

# =====================================================================
# Logging
# =====================================================================
logger = logging.getLogger("matching_engine")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S")
    )
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# =====================================================================
# Konstanta & default konfigurasi (mirror dari CONFIG pada notebook)
# =====================================================================
DEFAULT_SEP = {
    "student_all": ",",
    "status_student": ";",
    "tracking_student": ",",
    "tracking_company": ",",
    "talent_request": ",",
    "company": ",",
}

DEFAULT_COLS = {
    # status_student
    "s_nim": "NIM", "s_prodi": "program_studi", "s_tools": "tools",
    "s_ipk": "IPK", "s_cv": "CV", "s_porto": "portofolio",
    "s_semester": "semester", "s_status": "status",
    "s_avail": "ketersediaan", "s_name": "nama", "s_domisili": "domisili",
    "s_minat": "bidang_minat", "s_jenis_diminati": "jenis_penempatan_diminati",
    # talent_request
    "t_id": "id_talent_req", "t_company": "id_company",
    "t_company_name": "nama_perusahaan", "t_position": "nama_posisi",
    "t_req_text": "deskripsi_requirement", "t_bidang": "bidang_studi_dibutuhkan",
    "t_min_sem": "minimum_semester", "t_jenis": "jenis_penempatan",
    "t_headcount": "headcount",
    # talent_request -- sumber interest_score (bidang_minat mahasiswa vs
    # sektor industri perusahaan, lihat MINAT_INDUSTRI_COMPAT)
    "t_industri": "industri_sektor",
    # talent_request -- sumber location_score
    "t_alamat": "alamat_kantor", "t_wa": "working_arrangement",
    # tracking_student
    "ts_nim": "NIM", "ts_tc": "id_tracking_company", "ts_progress": "progress_student",
    # tracking_company
    "tc_id": "id_tracking_company", "tc_treq": "id_talent_req",
}

# Grade relevansi historis per tahap progress_student, dipakai untuk
# menandai pasangan (mahasiswa, talent_request) berlabel "sukses" saat
# membangun historical knowledge dictionary. Kalibrasi: kunci dict ini
# dulunya string tahap mentah, sekarang schema.STAGE_* -- sumber yang
# sama dipakai core/metrics.py (funnel_active_counts, funnel_drop_counts)
# untuk kolom progress_student yang identik.
DEFAULT_RELEVANCE_GRADE = {
    schema.STAGE_PLACEMENT: 3, schema.STAGE_FINISH: 3,
    schema.STAGE_FINAL: 2, schema.STAGE_INTERVIEW: 2, schema.STAGE_STUDYCASE: 2,
    schema.STAGE_FU1: 1, schema.STAGE_FU2: 1, schema.STAGE_FU3: 1,
    schema.STAGE_SELECTING: 1, schema.STAGE_BRIEFING: 1,
    schema.STAGE_REJECTED: 0, schema.STAGE_GHOSTING: 0,
}
DEFAULT_POSITIVE_MIN_REL = 2

# Kalibrasi: avail_available/avail_placed, status aktif, dan nilai CV/
# portofolio "ada" dulunya string lokal (AVAILABLE/PLACED/"Active"/"Ada").
# Sekarang semua dari core/schema.py, konsisten dengan definisi eligible
# BT-06 di core/metrics.is_eligible (ketersediaan == schema.AVAIL_AVAILABLE).
DEFAULT_ELIGIBILITY = {
    "avail_available": [schema.AVAIL_AVAILABLE],
    "avail_placed": [schema.AVAIL_PLACED],
    "status_active": [schema.STATUS_AKTIF, schema.STATUS_CUTI],
    "require_cv": True,
    "cv_positive": schema.CV_ADA,
    "porto_positive": schema.CV_ADA,  # portofolio pakai domain "Ada"/"Tidak Ada" yang sama dengan CV
}

DEFAULT_SYNONYMS = {
    "powerbi": "power bi", "power-bi": "power bi", "ms excel": "excel",
    "microsoft excel": "excel", "python3": "python", "postgresql": "sql",
    "mysql": "sql", "ms sql": "sql", "adobe ps": "adobe photoshop",
    "ps": "adobe photoshop", "ai": "adobe illustrator", "r studio": "r",
    "rstudio": "r", "power point": "powerpoint", "ms word": "word",
}

# Kompatibilitas bidang_minat mahasiswa (student_all.bidang_minat, 5 nilai
# domain tertutup: Teknologi, Bisnis, Sains, Sosial, Desain) vs
# industri_sektor talent_request (18 nilai domain tertutup: Retail,
# Asuransi, Teknologi Informasi, dst). Tabel kompatibilitas eksplisit
# (gaya sama dengan PLACEMENT_COMPAT di bawah), BUKAN keyword/text
# matching -- kedua kolom domain tertutup, jadi dipetakan langsung
# sebagai pasangan (minat, sektor) -> tier:
#   2 = sektor utama untuk minat itu (match kuat)
#   1 = sektor terkait/berdekatan (match sebagian)
#   (tidak terdaftar) = tidak relevan -> tier 0
# Heuristik ini sengaja tumpang tindih antar kategori (mis. "E-commerce"
# relevan untuk Teknologi, Bisnis, maupun Desain) karena domain aslinya
# memang tumpang tindih. interest_score dinormalisasi dari tier ini,
# lihat _match_interest() & calculate_component_scores().
MINAT_INDUSTRI_COMPAT = {
    ("teknologi", "teknologi informasi"): 2,
    ("teknologi", "telekomunikasi"): 2,
    ("teknologi", "e-commerce"): 2,
    ("teknologi", "otomotif"): 1,
    ("teknologi", "keuangan & perbankan"): 1,
    ("teknologi", "manufaktur"): 1,

    ("bisnis", "retail"): 2,
    ("bisnis", "asuransi"): 2,
    ("bisnis", "keuangan & perbankan"): 2,
    ("bisnis", "konsultan manajemen"): 2,
    ("bisnis", "fmcg"): 2,
    ("bisnis", "logistik & supply chain"): 2,
    ("bisnis", "otomotif"): 1,
    ("bisnis", "agribisnis"): 1,
    ("bisnis", "properti & konstruksi"): 1,
    ("bisnis", "travel & hospitality"): 1,
    ("bisnis", "e-commerce"): 1,
    ("bisnis", "manufaktur"): 1,

    ("sains", "energi & pertambangan"): 2,
    ("sains", "kesehatan & farmasi"): 2,
    ("sains", "manufaktur"): 2,
    ("sains", "agribisnis"): 2,
    ("sains", "otomotif"): 1,
    ("sains", "properti & konstruksi"): 1,
    ("sains", "telekomunikasi"): 1,
    ("sains", "teknologi informasi"): 1,

    ("sosial", "pendidikan & edtech"): 2,
    ("sosial", "travel & hospitality"): 2,
    ("sosial", "kesehatan & farmasi"): 2,
    ("sosial", "konsultan manajemen"): 1,
    ("sosial", "asuransi"): 1,
    ("sosial", "retail"): 1,
    ("sosial", "fmcg"): 1,

    ("desain", "media & kreatif"): 2,
    ("desain", "properti & konstruksi"): 2,
    ("desain", "e-commerce"): 2,
    ("desain", "retail"): 1,
    ("desain", "fmcg"): 1,
    ("desain", "pendidikan & edtech"): 1,
    ("desain", "teknologi informasi"): 1,
}
MINAT_INDUSTRI_TIER_MAX = 2  # dipakai untuk normalisasi tier -> interest_score 0..1

# Kompatibilitas jenis_penempatan_diminati (mahasiswa) vs jenis_penempatan
# (talent_request) -- domain tertutup 3 nilai (schema.JENIS_*). Sama
# persis -> 1.0. Magang/Part-time dianggap cukup kompatibel (sama-sama
# komitmen ringan bagi mahasiswa) -> skor menengah. Pasangan yang
# melibatkan Full-time -> skor rendah karena beda level komitmen.
PLACEMENT_COMPAT = {
    (schema.JENIS_MAGANG, schema.JENIS_PART_TIME): 0.6,
    (schema.JENIS_PART_TIME, schema.JENIS_MAGANG): 0.6,
    (schema.JENIS_MAGANG, schema.JENIS_FULL_TIME): 0.2,
    (schema.JENIS_FULL_TIME, schema.JENIS_MAGANG): 0.2,
    (schema.JENIS_PART_TIME, schema.JENIS_FULL_TIME): 0.3,
    (schema.JENIS_FULL_TIME, schema.JENIS_PART_TIME): 0.3,
}
PLACEMENT_COMPAT_DEFAULT = 0.2  # pasangan tak dikenal / data kosong

# Bobot INTERNAL sub-fitur rule-based untuk komponen yang memang
# merupakan agregat beberapa sub-fitur (tool_score, program_study_score).
# ipk_score/interest_score/location_score/placement_preference_score
# sudah berupa nilai 0..1 tunggal (atau raw/tier_max, lihat
# calculate_component_scores), tidak perlu subweight. Nilai ini TIDAK
# diexpose ke slider dashboard; yang diexpose adalah bobot 6 komponen di
# DEFAULT_WEIGHTS. req_semantic/has_cv/has_porto tidak ada di sini -- CV
# & semester murni gerbang eligibility (bukan skor), has_porto rencananya
# jadi filter tampilan (bukan skor), dan req_semantic tetap dihitung
# sebagai fitur informasional (lihat _features_for) tapi tidak diagregasi
# jadi komponen skor. ipk TIDAK di subweights ini karena ipk_score adalah
# komponen top-level tersendiri (murni IPK/4.0, tanpa sub-fitur lain).
DEFAULT_SUBWEIGHTS = {
    "prodi_exact": 2.0, "prodi_semantic": 1.5,
    "tool_coverage": 1.5, "tool_count": 0.5,
}

# Bobot komponen level-dashboard (real-time, dapat diubah slider).
# Kalibrasi: dulunya dict lokal, sekarang diambil dari config.BOBOT_DEFAULT
# (config.py Section 5.2, "All magic numbers, paths, thresholds, weights"),
# satu sumber default weight untuk Matching yang dipakai seluruh dashboard.
# Pemetaan komponen -> sub-fitur:
#   tool_match             : tool_coverage, tool_count (tools eksplisit + implicit)
#   program_study          : prodi_exact, prodi_semantic
#   ipk                    : ipk_score (IPK/4.0, murni faktor peringkat)
#   interest               : interest_score (bidang_minat vs industri_sektor, MINAT_INDUSTRI_COMPAT)
#   location                : location_score (domisili vs kota kantor, aktif saat WFO/Hybrid)
#   placement_preference   : placement_preference_score (jenis_penempatan_diminati)
# has_cv & minimum_semester TIDAK ada di sini -- keduanya gerbang
# eligibility (hard gate), bukan komponen skor. Lihat matching_gate() dan
# _build_base_pool().
DEFAULT_WEIGHTS = config.BOBOT_DEFAULT

DEFAULT_THRESHOLDS = {
    "prodi_semantic_min": 0.35,
    "req_semantic_min": 0.30,
    # Historical rule (keyword -> tool implicit): confidence minimum &
    # jumlah tool teratas per keyword yang dipakai sebagai suggested tools.
    # 0.15 dipilih empiris dari distribusi confidence pada data ini (top
    # confidence per keyword umumnya 0.06-0.21 karena tersebar di puluhan
    # tools yang mungkin) -- kira-kira persentil ke-90, supaya suggestion
    # hanya muncul untuk keyword dengan sinyal jelas di atas rata-rata,
    # bukan pada tiap keyword.
    "keyword_tool_min_conf": 0.15,
    "keyword_tool_top_k": 3,
}

# Stopwords untuk keyword-overlap rule-based (req_semantic, historical
# keyword dictionary). Kata umum ini dibuang supaya overlap mengukur
# kecocokan istilah bermakna, bukan kata penghubung.
STOPWORDS = {
    "yang", "dan", "atau", "dengan", "untuk", "dari", "pada", "ke", "di",
    "akan", "dapat", "bisa", "mampu", "serta", "juga", "memiliki", "adalah",
    "sebagai", "dalam", "atas", "ini", "itu", "para", "the", "and", "or",
    "to", "of", "in", "for", "a", "an", "is", "are", "with",
}


# =====================================================================
# Eligibility hard-gate -- sesuai spesifikasi wajib
# =====================================================================
def matching_gate(status_student: pd.DataFrame, minimum_semester: Optional[float]) -> pd.Series:
    """
    Hard gate sebelum proses scoring.

    Hanya mahasiswa yang memenuhi syarat yang diproses.
    Matching dilakukan setelah filtering, bukan melakukan matching
    terhadap seluruh mahasiswa.

    Parameters
    ----------
    status_student : DataFrame dengan kolom 'ketersediaan' dan 'semester'.
    minimum_semester : ambang semester minimum (None = tidak ada syarat).
    """
    avail = status_student["ketersediaan"] == schema.AVAIL_AVAILABLE

    if minimum_semester is None or (isinstance(minimum_semester, float) and np.isnan(minimum_semester)):
        return avail

    sem_ok = status_student["semester"] >= minimum_semester
    return avail & sem_ok


# =====================================================================
# MatchingEngine
# =====================================================================
class MatchingEngine:
    """
    Backend Rule-Based NLP Talent Matching, siap dipakai di Streamlit.

    Bisa diinisialisasi dengan:
    * ``paths``   : dict lokasi file CSV (seperti CONFIG['PATHS'] pada notebook), atau
    * ``dataframes`` : dict DataFrame yang sudah dimuat sebelumnya
      (keys: student_all, status_student, tracking_student,
      tracking_company, talent_request, company). Berguna bila
      Streamlit sudah membaca file lewat uploader, atau (kalibrasi)
      lewat core/loader.py + core/clean.py seperti setiap halaman lain
      di dashboard ini -- lihat pages/2_Matching.py.

    Semua parameter lain (cols, sep, eligibility, weights, thresholds,
    synonyms) opsional dan akan memakai default yang identik dengan
    notebook (varian rule-based) bila tidak diberikan.
    """

    REQUIRED_KEYS = (
        "student_all", "status_student", "tracking_student",
        "tracking_company", "talent_request", "company",
    )

    def __init__(
        self,
        paths: Optional[dict[str, str]] = None,
        dataframes: Optional[dict[str, pd.DataFrame]] = None,
        cols: Optional[dict[str, str]] = None,
        sep: Optional[dict[str, str]] = None,
        eligibility: Optional[dict[str, Any]] = None,
        weights: Optional[dict[str, float]] = None,
        subweights: Optional[dict[str, float]] = None,
        thresholds: Optional[dict[str, float]] = None,
        synonyms: Optional[dict[str, str]] = None,
        relevance_grade: Optional[dict[str, int]] = None,
        positive_min_rel: int = DEFAULT_POSITIVE_MIN_REL,
        random_state: int = 42,
        batch_size: int = 100,
        top_k_default: int = 25,
    ):
        if not paths and not dataframes:
            raise ValueError("Berikan salah satu dari 'paths' atau 'dataframes'.")

        self.paths = paths or {}
        self._input_dataframes = dataframes or {}
        self.cols = {**DEFAULT_COLS, **(cols or {})}
        self.sep = {**DEFAULT_SEP, **(sep or {})}
        self.eligibility = {**DEFAULT_ELIGIBILITY, **(eligibility or {})}
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self.subweights = {**DEFAULT_SUBWEIGHTS, **(subweights or {})}
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.synonyms = {**DEFAULT_SYNONYMS, **(synonyms or {})}
        self.relevance_grade = {**DEFAULT_RELEVANCE_GRADE, **(relevance_grade or {})}
        self.positive_min_rel = positive_min_rel
        self.random_state = random_state
        self.batch_size = batch_size
        self.top_k_default = top_k_default

        self._rng = np.random.default_rng(random_state)

        # state / precomputed artifacts
        self._initialized = False
        self.raw: dict[str, pd.DataFrame] = {}
        self.students_df: Optional[pd.DataFrame] = None
        self.talent_req_df: Optional[pd.DataFrame] = None
        self.hist: dict[str, Any] = {}

        # lookup structures built during precompute()
        self._tool_patterns: dict[str, re.Pattern] = {}
        self._tool_lexicon: list[str] = []
        self._city_lexicon: list[str] = []
        self._stu_prodi: dict[str, str] = {}
        self._stu_prodi_display: dict[str, str] = {}
        self._stu_tools: dict[str, set] = {}
        self._stu_ipk: dict[str, float] = {}
        self._stu_cv: dict[str, str] = {}
        self._stu_porto: dict[str, str] = {}
        self._stu_sem: dict[str, float] = {}
        self._stu_avail: dict[str, str] = {}
        self._stu_status: dict[str, str] = {}
        self._stu_name: dict[str, str] = {}
        self._stu_domisili: dict[str, str] = {}
        self._stu_minat: dict[str, str] = {}
        self._stu_jenis_diminati: dict[str, str] = {}

        self._req_full_by_tid: dict[str, str] = {}
        self._req_explicit_tools_by_tid: dict[str, list] = {}
        self._req_suggested_tools_by_tid: dict[str, list] = {}
        self._req_tools_by_tid: dict[str, list] = {}
        self._req_bidang_by_tid: dict[str, list] = {}
        self._req_minsem_by_tid: dict[str, float] = {}
        self._req_position_by_tid: dict[str, str] = {}
        self._req_wa_by_tid: dict[str, str] = {}
        self._req_kota_by_tid: dict[str, str] = {}
        self._req_jenis_by_tid: dict[str, str] = {}
        self._req_industri_by_tid: dict[str, str] = {}

        # NIM -> daftar request lain yang masih relevan (rejection ==
        # On Progress/Placement), dipakai untuk kolom "Request Lain" +
        # drill-down di dashboard. Lihat _build_other_request_lookup.
        self._other_request_by_nim: dict[str, list[dict]] = {}

        self._base_pool_nims: list[str] = []

        # caches (per talent_request_id)
        self._candidate_cache: dict[str, list[str]] = {}
        self._feature_cache: dict[str, pd.DataFrame] = {}
        self._component_cache: dict[str, pd.DataFrame] = {}

    # -----------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------
    @property
    def is_ready(self) -> bool:
        return self._initialized

    @property
    def total_students(self) -> int:
        """Jumlah seluruh mahasiswa di status_student (populasi keseluruhan,
        BUKAN base pool eligible). Dipakai sebagai penyebut KPI persentase
        mahasiswa eligible di dashboard."""
        return len(self.students_df) if self.students_df is not None else 0

    # -----------------------------------------------------------------
    # Public pipeline: load_data -> precompute -> initialize
    # -----------------------------------------------------------------
    def load_data(self) -> "MatchingEngine":
        """Muat seluruh CSV mentah (atau pakai DataFrame yang sudah diberikan)."""
        logger.info("Loading data...")
        for key in self.REQUIRED_KEYS:
            if key in self._input_dataframes:
                df = self._input_dataframes[key].copy()
            else:
                path = self.paths.get(key)
                if not path:
                    raise ValueError(f"Tidak ada path atau dataframe untuk '{key}'.")
                if not os.path.exists(path):
                    raise FileNotFoundError(
                        f"File '{path}' (key='{key}') tidak ditemukan. Periksa 'paths'."
                    )
                sep = self.sep.get(key, ",")
                df = pd.read_csv(path, sep=sep, dtype=str, keep_default_na=True)
            df.columns = [str(c).strip().lstrip("﻿") for c in df.columns]
            self.raw[key] = df
            logger.info("Loaded %-18s shape=%s", key, df.shape)
        return self

    def precompute(self) -> "MatchingEngine":
        """
        Jalankan seluruh proses mahal SATU KALI:
        preprocessing mahasiswa & talent request, tool lexicon, interest
        lexicon, historical knowledge dictionary (keyword -> tool rule).
        """
        if not self.raw:
            self.load_data()

        logger.info("Preprocessing students")
        self._preprocess_students()

        logger.info("Preprocessing talent requests")
        self._preprocess_talent_requests()

        logger.info("Building tool lexicon")
        self._build_tool_lexicon()
        self._extract_request_tools()

        logger.info("Building labeled pairs (historical)")
        _pairs, succ = self._build_labeled_pairs()

        logger.info("Learning historical keyword -> tool rule")
        self._build_historical_knowledge(succ)

        logger.info("Inferring suggested (implicit) tools per talent request")
        self._infer_suggested_tools()

        logger.info("Building base eligibility pool")
        self._base_pool_nims = self._build_base_pool()

        logger.info("Building cross-request lookup (Request Lain)")
        self._other_request_by_nim = self._build_other_request_lookup()

        self._initialized = True
        logger.info(
            "Precompute selesai. %d mahasiswa, %d talent request, %d tools, "
            "%d kandidat dasar eligible.",
            len(self.students_df), len(self.talent_req_df),
            len(self._tool_lexicon), len(self._base_pool_nims),
        )
        return self

    def initialize(self, force: bool = False) -> "MatchingEngine":
        """Entry point utama. Idempotent kecuali force=True."""
        if self._initialized and not force:
            logger.info("Engine sudah initialized, lewati precompute (pakai force=True untuk ulang).")
            return self
        self.precompute()
        return self

    # -----------------------------------------------------------------
    # 1-2. Preprocessing
    # -----------------------------------------------------------------
    def _get_col(self, df: pd.DataFrame, logical_name: str, label: str = "df") -> Optional[str]:
        real = self.cols.get(logical_name, logical_name)
        if real not in df.columns:
            logger.warning(
                "Kolom '%s' (logis '%s') tidak ditemukan di %s. Kolom tersedia: %s",
                real, logical_name, label, list(df.columns)[:12],
            )
            return None
        return real

    def _get_series(self, df: pd.DataFrame, logical_name: str, label: str = "df") -> pd.Series:
        real = self._get_col(df, logical_name, label)
        return df[real] if real is not None else pd.Series([np.nan] * len(df), index=df.index)

    @staticmethod
    def _normalize_text(s: Any) -> str:
        """Lowercase, samakan pemisah, buang karakter tak penting."""
        if pd.isna(s):
            return ""
        s = str(s).lower().strip()
        s = re.sub(r"[/|]", ",", s)
        s = re.sub(r"[^a-z0-9,.+\s#]", " ", s)
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    @staticmethod
    def _split_multi(s: Any) -> list[str]:
        """Pisah string multi-nilai (koma/slash/pipe) -> list token bersih."""
        if pd.isna(s):
            return []
        s = re.sub(r"[/|]", ",", str(s))
        return [t.strip().lower() for t in s.split(",") if t.strip()]

    @staticmethod
    def _to_float(x: Any, default: float = np.nan) -> float:
        try:
            return float(str(x).replace(",", "."))
        except Exception:
            return default

    def _apply_synonyms(self, tokens: list[str]) -> list[str]:
        return [self.synonyms.get(t, t) for t in tokens]

    def _preprocess_students(self) -> None:
        stat_std = self.raw["status_student"].copy()

        s_nim = self._get_col(stat_std, "s_nim", "status_student")
        s_avail = self._get_col(stat_std, "s_avail", "status_student")
        s_status = self._get_col(stat_std, "s_status", "status_student")
        s_ipk = self._get_col(stat_std, "s_ipk", "status_student")
        s_sem = self._get_col(stat_std, "s_semester", "status_student")
        s_cv = self._get_col(stat_std, "s_cv", "status_student")
        s_porto = self._get_col(stat_std, "s_porto", "status_student")
        s_name = self._get_col(stat_std, "s_name", "status_student")
        s_domisili = self._get_col(stat_std, "s_domisili", "status_student")
        s_prodi = self._get_col(stat_std, "s_prodi", "status_student")

        if s_nim:
            stat_std[s_nim] = stat_std[s_nim].astype(str).str.strip()
        if s_ipk:
            stat_std["_ipk"] = stat_std[s_ipk].apply(self._to_float)
        if s_sem:
            stat_std["_semester"] = pd.to_numeric(stat_std[s_sem], errors="coerce")

        stat_std["_tools_list"] = (
            self._get_series(stat_std, "s_tools", "status_student")
            .apply(self._split_multi)
            .apply(self._apply_synonyms)
        )
        stat_std["_prodi_norm"] = self._get_series(stat_std, "s_prodi", "status_student").apply(
            self._normalize_text
        )

        self.students_df = stat_std
        self._s_nim_col = s_nim

        idx = stat_std.set_index(s_nim) if s_nim else stat_std
        self._stu_prodi = idx["_prodi_norm"].to_dict()
        # Program studi apa adanya (case asli), untuk ditampilkan ke user.
        # _stu_prodi (di atas) sengaja dinormalisasi (lowercase) khusus untuk
        # scoring (_match_program_study/_prodi_bidang_sim), bukan untuk tampilan.
        self._stu_prodi_display = idx[s_prodi].to_dict() if s_prodi else {}
        self._stu_tools = {k: set(v) for k, v in idx["_tools_list"].to_dict().items()}
        self._stu_ipk = idx["_ipk"].to_dict() if "_ipk" in idx else {}
        self._stu_sem = idx["_semester"].to_dict() if "_semester" in idx else {}
        self._stu_cv = idx[s_cv].to_dict() if s_cv else {}
        self._stu_porto = idx[s_porto].to_dict() if s_porto else {}
        self._stu_avail = idx[s_avail].to_dict() if s_avail else {}
        self._stu_status = idx[s_status].to_dict() if s_status else {}
        self._stu_name = idx[s_name].to_dict() if s_name else {}
        self._stu_domisili = idx[s_domisili].to_dict() if s_domisili else {}

        # Kalibrasi/fitur baru: bidang_minat & jenis_penempatan_diminati
        # tidak ada di status_student, hanya di student_all. Join lewat
        # NIM (kolom bernama sama di kedua tabel, "s_nim" logical key
        # dipakai ulang). Belum pernah dipakai sebelumnya di modul ini.
        student_all = self.raw["student_all"].copy()
        sa_nim = self._get_col(student_all, "s_nim", "student_all")
        sa_minat = self._get_col(student_all, "s_minat", "student_all")
        sa_jenis = self._get_col(student_all, "s_jenis_diminati", "student_all")
        if sa_nim:
            student_all[sa_nim] = student_all[sa_nim].astype(str).str.strip()
        idx_sa = student_all.set_index(sa_nim) if sa_nim else student_all
        self._stu_minat = idx_sa[sa_minat].to_dict() if sa_minat else {}
        self._stu_jenis_diminati = idx_sa[sa_jenis].to_dict() if sa_jenis else {}

        # Lexicon kota, untuk fallback ekstraksi kota kantor (lihat
        # _preprocess_talent_requests / _extract_kota). Domisili mahasiswa
        # adalah nama kota bersih, sumber yang jauh lebih kecil & bersih
        # daripada mem-parsing alamat bebas dari nol.
        cities = {str(v).strip() for v in self._stu_domisili.values() if v and not pd.isna(v)}
        self._city_lexicon = sorted(cities, key=len, reverse=True)

    def _preprocess_talent_requests(self) -> None:
        talent_req = self.raw["talent_request"].copy()

        t_id = self._get_col(talent_req, "t_id", "talent_request")
        talent_req["_req_norm"] = self._get_series(talent_req, "t_req_text", "talent_request").apply(
            self._normalize_text
        )
        talent_req["_bidang_list"] = self._get_series(talent_req, "t_bidang", "talent_request").apply(
            self._split_multi
        )
        talent_req["_pos_norm"] = self._get_series(talent_req, "t_position", "talent_request").apply(
            self._normalize_text
        )
        bidang_text = self._get_series(talent_req, "t_bidang", "talent_request").fillna("").apply(
            self._normalize_text
        )
        talent_req["_req_full"] = (
            talent_req["_req_norm"] + " . " + talent_req["_pos_norm"] + " . " + bidang_text
        ).str.strip()

        # Fitur baru: kota kantor, dari alamat_kantor (teks bebas, format
        # umum "Jl. ..., <Kota>"). Segmen terakhir setelah koma adalah
        # kota pada seluruh data ini; fallback ke pencarian lexicon kota
        # (dibangun dari domisili mahasiswa) bila format berbeda.
        talent_req["_kota_kantor"] = self._get_series(talent_req, "t_alamat", "talent_request").apply(
            self._extract_kota
        )

        # Sektor industri perusahaan, sumber interest_score (lihat
        # MINAT_INDUSTRI_COMPAT / _match_interest). Domain tertutup,
        # dinormalisasi (lower+strip) supaya cocok dengan key tabel.
        talent_req["_industri_norm"] = self._get_series(
            talent_req, "t_industri", "talent_request"
        ).apply(lambda s: "" if pd.isna(s) else str(s).strip().lower())

        if t_id:
            talent_req[t_id] = talent_req[t_id].astype(str).str.strip()

        self.talent_req_df = talent_req
        self._t_id_col = t_id

        min_sem_col = self._get_col(talent_req, "t_min_sem", "talent_request")
        wa_col = self._get_col(talent_req, "t_wa", "talent_request")
        jenis_col = self._get_col(talent_req, "t_jenis", "talent_request")
        idx = talent_req.set_index(t_id) if t_id else talent_req
        self._req_full_by_tid = idx["_req_full"].to_dict()
        self._req_bidang_by_tid = idx["_bidang_list"].to_dict()
        self._req_minsem_by_tid = (
            pd.to_numeric(idx[min_sem_col], errors="coerce").to_dict() if min_sem_col else {}
        )
        pos_col = self._get_col(talent_req, "t_position", "talent_request")
        self._req_position_by_tid = idx[pos_col].to_dict() if pos_col else {}
        self._req_wa_by_tid = idx[wa_col].to_dict() if wa_col else {}
        self._req_jenis_by_tid = idx[jenis_col].to_dict() if jenis_col else {}
        self._req_kota_by_tid = idx["_kota_kantor"].to_dict()
        self._req_industri_by_tid = idx["_industri_norm"].to_dict()

    def _extract_kota(self, alamat: Any) -> str:
        """Ekstrak nama kota dari alamat_kantor (rule-based, bukan geocoding).

        Format alamat pada data ini konsisten "<jalan>, <Kota>": segmen
        setelah koma terakhir adalah kotanya. Fallback: cari nama kota
        yang dikenal (dari domisili mahasiswa) di dalam teks alamat.
        """
        if not isinstance(alamat, str) or not alamat.strip():
            return ""
        last = alamat.split(",")[-1].strip()
        if last:
            return last
        low = alamat.lower()
        for city in self._city_lexicon:
            if city.lower() in low:
                return city
        return ""

    # -----------------------------------------------------------------
    # 3. Tool lexicon & ekstraksi tools dari requirement (NLP)
    # -----------------------------------------------------------------
    def _build_tool_lexicon(self) -> None:
        counter: Counter = Counter()
        for lst in self.students_df["_tools_list"]:
            counter.update(lst)
        lexicon = sorted([t for t in counter if len(t) >= 2 and not t.isdigit()])
        self._tool_lexicon = lexicon
        self._tool_patterns = {
            t: re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])") for t in lexicon
        }
        logger.info("Tool lexicon: %d tools terdeteksi dari data mahasiswa.", len(lexicon))

    def _extract_tools(self, text_norm: str) -> list[str]:
        """Temukan tools dari lexicon yang muncul di teks ternormalisasi (NLP extraction)."""
        if not text_norm:
            return []
        found = [t for t, pat in self._tool_patterns.items() if pat.search(text_norm)]
        return self._apply_synonyms(found)

    def _extract_request_tools(self) -> None:
        """Tools EKSPLISIT per talent request (regex lexicon di teks requirement).

        Ini sumber pertama dari dua sumber tools_dibutuhkan; sumber kedua
        (implicit/suggested, dari historical rule) ditambahkan belakangan
        oleh _infer_suggested_tools() setelah historical dictionary siap.
        """
        self.talent_req_df["_req_tools"] = self.talent_req_df["_req_full"].apply(self._extract_tools)
        idx = (
            self.talent_req_df.set_index(self._t_id_col)
            if self._t_id_col
            else self.talent_req_df
        )
        self._req_explicit_tools_by_tid = idx["_req_tools"].to_dict()
        coverage = (self.talent_req_df["_req_tools"].apply(len) > 0).mean()
        logger.info("Talent request dengan >=1 tool eksplisit terdeteksi: %.1f%%", 100 * coverage)

    # -----------------------------------------------------------------
    # 4. Pasangan berlabel historis (untuk historical knowledge dict)
    # -----------------------------------------------------------------
    def _build_labeled_pairs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        track_std = self.raw["tracking_student"].copy()
        track_comp = self.raw["tracking_company"].copy()

        ts_nim = self._get_col(track_std, "ts_nim", "tracking_student")
        ts_tc = self._get_col(track_std, "ts_tc", "tracking_student")
        ts_prog = self._get_col(track_std, "ts_progress", "tracking_student")
        tc_id = self._get_col(track_comp, "tc_id", "tracking_company")
        tc_treq = self._get_col(track_comp, "tc_treq", "tracking_company")

        pos = track_std[[ts_nim, ts_tc, ts_prog]].copy()
        pos = pos.merge(track_comp[[tc_id, tc_treq]], left_on=ts_tc, right_on=tc_id, how="left")
        pos = pos.rename(columns={ts_nim: "NIM", tc_treq: "tid"})
        pos["NIM"] = pos["NIM"].astype(str)
        pos["tid"] = pos["tid"].astype(str)
        pos["rel"] = pos[ts_prog].map(self.relevance_grade).fillna(0).astype(int)
        pos["label"] = (pos["rel"] >= self.positive_min_rel).astype(int)
        pos = (
            pos[["NIM", "tid", "rel", "label"]]
            .dropna(subset=["tid"])
            .sort_values("rel", ascending=False)
            .drop_duplicates(["NIM", "tid"], keep="first")
        )

        s_nim = self._s_nim_col
        succ = pos[pos["rel"] >= self.positive_min_rel].merge(
            self.students_df[[s_nim, "_prodi_norm", "_tools_list"]],
            left_on="NIM", right_on=s_nim, how="left",
        )
        succ = succ.merge(
            self.talent_req_df[[self._t_id_col, "_req_full"]],
            left_on="tid", right_on=self._t_id_col, how="left",
        )
        return pos, succ

    # -----------------------------------------------------------------
    # 5. Historical Knowledge -- BUKAN komponen skor. Dipakai murni untuk
    # mempelajari rule "requirement keyword -> tools yang biasa dimiliki
    # mahasiswa yang berhasil ditempatkan", lalu dipakai memperkaya daftar
    # tools_dibutuhkan sebuah talent request (lihat _infer_suggested_tools).
    # Tidak ada historical_score/hist_confidence/popularity lagi.
    # -----------------------------------------------------------------
    @staticmethod
    def _top_with_conf(counter: Counter, n: int = 10) -> list[tuple[str, float]]:
        total = sum(counter.values())
        if total == 0:
            return []
        return [(k, round(v / total, 4)) for k, v in counter.most_common(n)]

    def _build_historical_knowledge(self, succ: pd.DataFrame) -> None:
        """Pelajari keyword_requirement -> {tool: confidence} dari placement sukses.

        Untuk tiap pasangan (mahasiswa, talent_request) yang berhasil
        ditempatkan (rel >= positive_min_rel), setiap keyword bermakna di
        teks requirement (_req_full, keyword_tokens sama seperti
        _match_requirement) "memberi suara" ke setiap tool yang dimiliki
        mahasiswa tersebut. confidence(tool | keyword) = proporsi voting
        tool itu dari semua voting untuk keyword itu.
        """
        keyword_tool: dict = defaultdict(Counter)

        for _, r in succ.iterrows():
            tlist = r["_tools_list"] if isinstance(r["_tools_list"], list) else []
            if not tlist:
                continue
            req_keywords = self._keyword_tokens(r["_req_full"] or "")
            for kw in req_keywords:
                for t in tlist:
                    keyword_tool[kw][t] += 1

        self.hist = {
            "keyword_tools": {kw: self._top_with_conf(c) for kw, c in keyword_tool.items()},
        }
        logger.info(
            "Historical keyword->tool rule siap (%d keyword requirement dipelajari).",
            len(keyword_tool),
        )

    def _infer_suggested_tools(self) -> None:
        """Tools implicit/"suggested" per talent request dari historical rule.

        Untuk tiap keyword bermakna di teks requirement, ambil tool
        teratas (top keyword_tool_top_k) dengan confidence >=
        keyword_tool_min_conf dari hist["keyword_tools"]. Tools yang
        sudah disebut eksplisit tidak diulang di sini. Requirement tools
        yang dipakai downstream (_match_tools) = eksplisit UNION suggested.
        """
        keyword_tools = self.hist.get("keyword_tools", {})
        min_conf = self.thresholds["keyword_tool_min_conf"]
        top_k = int(self.thresholds["keyword_tool_top_k"])

        suggested_by_tid: dict[str, list] = {}
        for tid, text in self._req_full_by_tid.items():
            keywords = self._keyword_tokens(text or "")
            found: set = set()
            for kw in keywords:
                for tool, conf in keyword_tools.get(kw, [])[:top_k]:
                    if conf >= min_conf:
                        found.add(tool)
            explicit = set(self._req_explicit_tools_by_tid.get(tid, []) or [])
            suggested_by_tid[tid] = sorted(found - explicit)

        self._req_suggested_tools_by_tid = suggested_by_tid
        self._req_tools_by_tid = {
            tid: sorted(set(self._req_explicit_tools_by_tid.get(tid, [])) | set(suggested_by_tid.get(tid, [])))
            for tid in self._req_full_by_tid
        }
        with_suggestion = sum(1 for v in suggested_by_tid.values() if v)
        logger.info(
            "Talent request dengan >=1 tool implicit (historical rule): %.1f%%",
            100 * with_suggestion / max(1, len(suggested_by_tid)),
        )

    # -----------------------------------------------------------------
    # 6. Text-similarity rule-based (pengganti semantic embedding)
    # -----------------------------------------------------------------
    # Notebook membandingkan varian "Rule saja" vs "Rule+Semantic"
    # (sentence-transformers/TF-IDF). Semantic embedding TERBUKTI
    # menurunkan performa walau menambah kompleksitas & dependency berat,
    # sehingga kemiripan teks di sini dihitung murni rule-based:
    #   * prodi vs bidang requirement -> fuzzy string ratio (difflib)
    #   * profil mahasiswa vs teks requirement -> keyword overlap (Jaccard)
    # Keduanya deterministik, tidak butuh model eksternal, dan bisa
    # dihitung langsung per-pasangan (tanpa precompute embedding).
    @staticmethod
    def _fuzzy_ratio(a: str, b: str) -> float:
        """Kemiripan string 0..1 berbasis longest-matching-blocks (SequenceMatcher)."""
        if not a or not b:
            return 0.0
        return difflib.SequenceMatcher(None, a, b).ratio()

    def _prodi_bidang_sim(self, prodi_norm: str, bidang_list: list[str]) -> float:
        """Kemiripan program studi vs bidang yang dibutuhkan (rule-based fuzzy ratio)."""
        if not prodi_norm or not bidang_list:
            return 0.0
        return max((self._fuzzy_ratio(prodi_norm, b) for b in bidang_list), default=0.0)

    def _student_profile_text(self, nim: str) -> str:
        p = self._stu_prodi.get(nim, "")
        t = " ".join(self._stu_tools.get(nim, []))
        return (p + " . " + t).strip()

    @staticmethod
    def _keyword_tokens(text: str) -> set:
        """Tokenisasi kata bermakna (buang stopword & kata sangat pendek)."""
        if not text:
            return set()
        return {t for t in text.split() if len(t) >= 3 and t not in STOPWORDS}

    def _match_requirement(self, nim: str, tid: str) -> float:
        """
        Keyword coverage rule-based: proporsi kata kunci pada teks
        requirement yang juga muncul pada profil mahasiswa (prodi + tools).
        """
        req_tokens = self._keyword_tokens(self._req_full_by_tid.get(tid, ""))
        if not req_tokens:
            return 0.0
        profile_tokens = self._keyword_tokens(self._student_profile_text(nim))
        if not profile_tokens:
            return 0.0
        return len(profile_tokens & req_tokens) / len(req_tokens)

    def _match_interest(self, nim: str, tid: str) -> int:
        """
        interest_raw, tier 0/1/2: kecocokan bidang_minat mahasiswa
        (student_all.bidang_minat) vs industri_sektor talent request.
        Tabel kompatibilitas eksplisit (MINAT_INDUSTRI_COMPAT), BUKAN
        keyword/text matching -- kedua kolom domain tertutup. 2 = sektor
        utama, 1 = sektor terkait, 0 = tidak terdaftar/data kosong.
        Nilai raw ini dinormalisasi jadi interest_score 0..1 di
        calculate_component_scores() (raw & normalisasi disimpan terpisah).
        """
        minat = self._stu_minat.get(nim, "")
        if not minat or (isinstance(minat, float) and pd.isna(minat)):
            return 0
        industri = self._req_industri_by_tid.get(tid, "")
        if not industri:
            return 0
        return MINAT_INDUSTRI_COMPAT.get((str(minat).strip().lower(), industri), 0)

    def _match_location(self, nim: str, tid: str) -> float:
        """
        location_score, 0..1: domisili mahasiswa vs kota kantor talent
        request (_extract_kota dari alamat_kantor). Aktif hanya saat
        working_arrangement WFO/Hybrid (schema.WA_DOMISILI_ACTIVE) --
        untuk WFH lokasi tidak relevan, location_score = 1 (tidak
        menjadi diskriminator). WFO: kota sama -> 1, beda -> 0. Hybrid:
        kota sama -> 1, beda -> 0.5 (lebih longgar). Tidak ada tingkat
        kabupaten/provinsi: dataset ini tidak punya tabel referensi
        kota->provinsi resmi, jadi tingkat itu disengaja tidak dibuat
        (spesifikasi menandainya opsional bila tersedia mapping).
        """
        wa = self._req_wa_by_tid.get(tid, "")
        if wa not in schema.WA_DOMISILI_ACTIVE:
            return 1.0

        domisili = self._stu_domisili.get(nim, "")
        kota_kantor = self._req_kota_by_tid.get(tid, "")
        if not domisili or not kota_kantor or pd.isna(domisili):
            return 0.5  # data tidak lengkap -> netral, bukan dihukum

        same = self._normalize_text(domisili) == self._normalize_text(kota_kantor)
        if same:
            return 1.0
        return 0.5 if wa == schema.WA_HYBRID else 0.0

    def _match_placement_preference(self, nim: str, tid: str) -> float:
        """
        placement_preference_score, 0..1: jenis_penempatan_diminati
        mahasiswa (student_all) vs jenis_penempatan talent request. Sama
        persis -> 1.0. Pasangan lain dari domain tertutup 3 nilai
        (Magang/Part-time/Full-time) -> lihat PLACEMENT_COMPAT.
        """
        diminati = self._stu_jenis_diminati.get(nim, "")
        diminta = self._req_jenis_by_tid.get(tid, "")
        if not diminati or not diminta or pd.isna(diminati):
            return 0.5  # preferensi tidak tercatat -> netral
        if diminati == diminta:
            return 1.0
        return PLACEMENT_COMPAT.get((diminati, diminta), PLACEMENT_COMPAT_DEFAULT)

    # -----------------------------------------------------------------
    # 7. Feature engineering per pasangan (nim, tid) -- inti rule-based
    # -----------------------------------------------------------------
    def _match_tools(self, nim: str, tid: str) -> dict:
        """
        Tools eksplisit + implicit (union, lihat _infer_suggested_tools)
        vs tools mahasiswa. matched_tools/matched_suggested_tools
        disimpan sampai output recommendation (lihat _format_output),
        supaya dashboard tidak perlu menghitung ulang.
        """
        tools = self._stu_tools.get(nim, set())
        rtools_explicit = set(self._req_explicit_tools_by_tid.get(tid, []) or [])
        rtools_suggested = set(self._req_suggested_tools_by_tid.get(tid, []) or [])
        rtools = rtools_explicit | rtools_suggested
        inter = tools & rtools
        inter_suggested = tools & rtools_suggested
        return {
            "tool_count": len(inter),
            "tool_coverage": (len(inter) / len(rtools)) if rtools else 0.0,
            "tool_coverage_student": (len(inter) / len(tools)) if tools else 0.0,
            "matched_tools": sorted(inter),
            "matched_suggested_tools": sorted(inter_suggested),
        }

    def _match_program_study(self, nim: str, tid: str) -> dict:
        prodi = self._stu_prodi.get(nim, "")
        bidang = self._req_bidang_by_tid.get(tid, []) or []
        bidang_norm = [self._normalize_text(b) for b in bidang]
        prodi_exact = 1.0 if any(prodi == b for b in bidang_norm) else 0.0
        prodi_semantic = self._prodi_bidang_sim(prodi, bidang_norm)
        return {"prodi_exact": prodi_exact, "prodi_semantic": prodi_semantic}

    def _features_for(self, nim: str, tid: str) -> dict:
        program_study = self._match_program_study(nim, tid)
        tools = self._match_tools(nim, tid)
        req_sem = self._match_requirement(nim, tid)
        interest_raw = self._match_interest(nim, tid)
        location = self._match_location(nim, tid)
        placement_pref = self._match_placement_preference(nim, tid)

        has_cv = 1.0 if str(self._stu_cv.get(nim, "")).strip() == self.eligibility["cv_positive"] else 0.0
        has_porto = 1.0 if str(self._stu_porto.get(nim, "")).strip() == self.eligibility["porto_positive"] else 0.0
        ipk = self._stu_ipk.get(nim, np.nan)
        ipk = ipk if ipk == ipk else 0.0
        sem = self._stu_sem.get(nim, np.nan)
        min_sem = self._req_minsem_by_tid.get(tid, np.nan)
        semester_ok = (
            1.0 if (sem == sem and min_sem == min_sem and sem >= min_sem)
            else (0.0 if min_sem == min_sem else 1.0)
        )

        return {
            "NIM": nim,
            "prodi_exact": program_study["prodi_exact"],
            "prodi_semantic": program_study["prodi_semantic"],
            "tool_count": tools["tool_count"],
            "tool_coverage": tools["tool_coverage"],
            "tool_coverage_student": tools["tool_coverage_student"],
            "matched_tools": tools["matched_tools"],
            "matched_suggested_tools": tools["matched_suggested_tools"],
            "req_semantic": req_sem,
            "interest_raw": interest_raw,
            "location_score": location,
            "placement_preference_score": placement_pref,
            "has_cv": has_cv,
            "has_porto": has_porto,
            "ipk": ipk,
            "semester_ok": semester_ok,
        }

    # -----------------------------------------------------------------
    # 10. Eligibility filter (candidate pool) -- WAJIB dijalankan dulu
    # (TIDAK diubah oleh refactor ini)
    # -----------------------------------------------------------------
    def _build_base_pool(self) -> list[str]:
        """Business-rule dasar (tidak tergantung talent request tertentu)."""
        df = self.students_df.copy()
        n0 = len(df)
        avail = df["_" + "avail_norm"] = self._get_series(df, "s_avail", "status_student").astype(str).str.strip()
        status = self._get_series(df, "s_status", "status_student").astype(str).str.strip()

        placed_mask = avail.isin(self.eligibility["avail_placed"])
        df = df[~placed_mask]
        avail = avail.loc[df.index]
        df = df[avail.isin(self.eligibility["avail_available"])]

        status = status.loc[df.index]
        df = df[status.isin(self.eligibility["status_active"])]

        if self.eligibility.get("require_cv") and self._get_col(self.students_df, "s_cv", "status_student"):
            cv_col = self._get_col(self.students_df, "s_cv", "status_student")
            df = df[df[cv_col].astype(str).str.strip() == self.eligibility["cv_positive"]]

        nims = df[self._s_nim_col].astype(str).tolist()
        logger.info("Base eligible pool: %d dari %d mahasiswa (Placed dikeluarkan: %d).",
                    len(nims), n0, int(placed_mask.sum()))
        return nims

    # -----------------------------------------------------------------
    # "Request Lain" -- request lain di mana seorang NIM masih aktif atau
    # sudah berhasil. Dipakai untuk kolom Request Lain/Jumlah Request Lain
    # + drill-down di dashboard (BUKAN komponen skor -- murni informasi,
    # sama seperti Alasan).
    # -----------------------------------------------------------------
    def _build_other_request_lookup(self) -> dict[str, list[dict]]:
        """NIM -> daftar request lain yang masih relevan, terurut tanggal.

        Sumber: tracking_student (satu baris per proses kandidat, kolom
        rejection) di-join ke tracking_company (id_tracking_company ->
        id_talent_req, send_date) -- BUKAN tracking_company.list_nim_bersih,
        supaya dua aturan bisnis berikut bisa ditegakkan:

        * Request yang SUDAH rejection (rejection bukan
          schema.REJ_ONPROGRESS atau schema.REJ_PLACEMENT -- artinya sudah
          gugur di salah satu tahap seleksi atau ghosting) TIDAK dihitung:
          kandidat itu sudah tidak lagi "menempati" request tersebut.
        * Request yang sama dihitung SATU KALI, berapa pun jumlah baris
          prosesnya (mis. beberapa tahap funnel tercatat terpisah).

        Diurutkan menaik berdasarkan tanggal (send_date, fallback
        last_update bila send_date kosong) supaya other_requests() bisa
        menampilkan riwayat kandidat secara kronologis.
        """
        ts = self.raw.get("tracking_student")
        tc = self.raw.get("tracking_company")
        if ts is None or tc is None or ts.empty or tc.empty:
            return {}

        ts_nim = self._get_col(ts, "ts_nim", "tracking_student")
        ts_tc = self._get_col(ts, "ts_tc", "tracking_student")
        tc_id = self._get_col(tc, "tc_id", "tracking_company")
        tc_treq = self._get_col(tc, "tc_treq", "tracking_company")
        if not (ts_nim and ts_tc and tc_id and tc_treq) or "rejection" not in ts.columns:
            return {}

        ts_cols = [ts_nim, ts_tc, "rejection"]
        if "last_update" in ts.columns:
            ts_cols.append("last_update")
        tc_cols = [tc_id, tc_treq]
        tc_cols += [c for c in ("send_date", "posisi", "nama_perusahaan") if c in tc.columns]

        ts_slim = ts[ts_cols].rename(columns={ts_nim: "NIM", ts_tc: "_tc_id"})
        tc_slim = tc[tc_cols].rename(columns={tc_id: "_tc_id", tc_treq: "tid"})
        merged = ts_slim.merge(tc_slim, on="_tc_id", how="left")

        # On Progress & Placement masih dianggap "menempati" request itu;
        # nilai rejection lain (Rejection Screening CV/Study Case/Interview/
        # Final Interview, Ghosting) berarti kandidat sudah keluar dari
        # request tersebut.
        active = merged[merged["rejection"].isin([schema.REJ_ONPROGRESS, schema.REJ_PLACEMENT])].copy()
        active["NIM"] = active["NIM"].astype(str).str.strip()
        active["tid"] = active["tid"].astype(str).str.strip()
        active = active[
            (active["NIM"] != "") & (active["tid"] != "") & (active["tid"].str.lower() != "nan")
        ]

        if "send_date" in active.columns and "last_update" in active.columns:
            active["_tanggal"] = active["send_date"].fillna(active["last_update"])
        elif "send_date" in active.columns:
            active["_tanggal"] = active["send_date"]
        elif "last_update" in active.columns:
            active["_tanggal"] = active["last_update"]
        else:
            active["_tanggal"] = pd.NaT
        active = active.sort_values("_tanggal")

        lookup: dict[str, list[dict]] = defaultdict(list)
        seen: dict[str, set] = defaultdict(set)
        for rec in active.to_dict("records"):
            nim, tid = rec["NIM"], rec["tid"]
            if tid in seen[nim]:
                continue  # request yang sama, berapa pun prosesnya, dihitung 1
            seen[nim].add(tid)
            lookup[nim].append({
                "id_talent_req": tid,
                "posisi": rec.get("posisi", ""),
                "perusahaan": rec.get("nama_perusahaan", ""),
                "tanggal": rec.get("_tanggal"),
            })
        return dict(lookup)

    def other_requests(self, nim: str, exclude_tid: Optional[str] = None) -> list[dict]:
        """Daftar request lain (id_talent_req, posisi, perusahaan, tanggal)
        di mana NIM ini masih aktif atau sudah berhasil, terurut menaik
        berdasarkan tanggal. exclude_tid biasanya request yang sedang
        dilihat di dashboard."""
        exclude = str(exclude_tid) if exclude_tid is not None else None
        return [
            dict(r) for r in self._other_request_by_nim.get(str(nim), [])
            if r["id_talent_req"] != exclude
        ]

    def other_request_count(self, nim: str, exclude_tid: Optional[str] = None) -> int:
        """Jumlah request LAIN (selain exclude_tid) yang masih relevan untuk NIM ini."""
        return len(self.other_requests(nim, exclude_tid))

    def other_request_label(self, nim: str, exclude_tid: Optional[str] = None) -> str:
        """Label human-readable untuk kolom Request Lain di dashboard."""
        count = self.other_request_count(nim, exclude_tid)
        if count == 0:
            return "Tidak berada dalam request lain"
        return f"Sedang berada di {count} request"

    def filter_candidates(self, talent_request_id: str) -> list[str]:
        """
        Eligibility filtering (hard gate) untuk sebuah talent request.
        Hasil di-cache per talent_request_id.
        """
        tid = str(talent_request_id)
        if tid in self._candidate_cache:
            return self._candidate_cache[tid]

        if tid not in self._req_full_by_tid:
            raise KeyError(f"Talent request '{tid}' tidak ditemukan.")

        min_sem = self._req_minsem_by_tid.get(tid, np.nan)
        min_sem = None if (min_sem != min_sem) else float(min_sem)  # NaN -> None

        base_df = self.students_df[self.students_df[self._s_nim_col].astype(str).isin(self._base_pool_nims)]
        gate_input = pd.DataFrame({
            "ketersediaan": self._get_series(base_df, "s_avail", "status_student").astype(str).str.strip(),
            "semester": base_df["_semester"] if "_semester" in base_df else np.nan,
        }, index=base_df.index)

        mask = matching_gate(gate_input, min_sem)
        eligible_nims = base_df.loc[mask, self._s_nim_col].astype(str).tolist()

        logger.info("Filtering candidates untuk %s: %d eligible (dari %d base pool).",
                    tid, len(eligible_nims), len(self._base_pool_nims))
        self._candidate_cache[tid] = eligible_nims
        return eligible_nims

    # -----------------------------------------------------------------
    # Matching (fitur mentah, di-cache per talent_request_id)
    # (TIDAK diubah oleh refactor ini -- hanya kolom fitur yang berbeda)
    # -----------------------------------------------------------------
    def match(self, talent_request_id: str, candidate_nims: Optional[list[str]] = None,
              top_n: Optional[int] = None) -> pd.DataFrame:
        """
        Hitung fitur rule-based untuk seluruh kandidat vs sebuah talent
        request. Hasil di-cache; dipanggil ulang hanya bila cache
        dikosongkan lewat `clear_cache()`.

        Bila `top_n` kosong (None), kandidat diproses per-batch
        (`self.batch_size`, default 100 baris mahasiswa) agar efisien
        untuk ribuan mahasiswa alih-alih membangun satu matriks fitur
        raksasa sekaligus.
        """
        tid = str(talent_request_id)
        if tid in self._feature_cache:
            return self._feature_cache[tid]

        nims = candidate_nims if candidate_nims is not None else self.filter_candidates(tid)
        if not nims:
            logger.warning("Tidak ada kandidat eligible untuk talent request %s.", tid)
            empty = pd.DataFrame(columns=[
                "NIM", "prodi_exact", "prodi_semantic", "tool_count", "tool_coverage",
                "tool_coverage_student", "matched_tools", "matched_suggested_tools",
                "req_semantic", "interest_raw", "location_score",
                "placement_preference_score", "has_cv", "has_porto", "ipk", "semester_ok",
            ])
            self._feature_cache[tid] = empty
            return empty

        batch_size = self.batch_size if top_n is None else max(self.batch_size, len(nims))
        logger.info("Matching tools & requirements untuk %s: %d kandidat (batch=%d).",
                    tid, len(nims), batch_size)

        rows: list[dict] = []
        n_batches = (len(nims) + batch_size - 1) // batch_size
        for bi in range(0, len(nims), batch_size):
            batch = nims[bi: bi + batch_size]
            rows.extend(self._features_for(n, tid) for n in batch)
            logger.info("  batch %d/%d selesai (%d/%d mahasiswa).",
                        bi // batch_size + 1, n_batches, min(bi + batch_size, len(nims)), len(nims))

        fdf = pd.DataFrame(rows)
        self._feature_cache[tid] = fdf
        logger.info("Computing score selesai untuk %s.", tid)
        return fdf

    # -----------------------------------------------------------------
    # Component scoring (cached, murah untuk dihitung ulang)
    # 6 komponen: tool, program_study, ipk, interest, location,
    # placement_preference. Tidak ada lagi komponen historical maupun
    # requirement gabungan (CV & minimum_semester adalah hard gate, bukan
    # skor -- lihat matching_gate()/_build_base_pool(); has_porto rencananya
    # jadi filter tampilan, bukan skor). ipk berdiri sendiri sebagai
    # komponen skor murni (bukan gerbang) atas permintaan eksplisit --
    # dipakai untuk menentukan peringkat, bukan menyaring eligibility.
    # -----------------------------------------------------------------
    def calculate_component_scores(self, talent_request_id: str, feature_df: Optional[pd.DataFrame] = None
                                    ) -> pd.DataFrame:
        """
        Agregasi sub-fitur rule-based menjadi 6 komponen skor
        (tool_score, program_study_score, ipk_score, interest_score,
        location_score, placement_preference_score), masing-masing 0..1.
        Di-cache per tid.
        """
        tid = str(talent_request_id)
        if tid in self._component_cache:
            return self._component_cache[tid]

        fdf = feature_df if feature_df is not None else self.match(tid)
        if fdf.empty:
            self._component_cache[tid] = fdf
            return fdf

        w = self.subweights
        df = fdf.copy()

        # --- tool_match component ---
        tool_wsum = abs(w["tool_coverage"]) + abs(w["tool_count"])
        df["tool_score"] = (
            w["tool_coverage"] * df["tool_coverage"]
            + w["tool_count"] * (df["tool_count"].clip(upper=5) / 5.0)
        ) / (tool_wsum or 1.0)

        # --- program_study component ---
        prodi_wsum = abs(w["prodi_exact"]) + abs(w["prodi_semantic"])
        df["program_study_score"] = (
            w["prodi_exact"] * df["prodi_exact"] + w["prodi_semantic"] * df["prodi_semantic"]
        ) / (prodi_wsum or 1.0)

        # --- ipk component: IPK/4.0, murni faktor peringkat (bukan gerbang
        # eligibility -- itu tugas CV & minimum_semester, lihat
        # matching_gate()/_build_base_pool()). ipk mentah (skala 0..4)
        # tetap disimpan apa adanya di kolom feature_df; ipk_score di sini
        # adalah versi ternormalisasi (0..1) yang dipakai untuk final_score.
        df["ipk_score"] = (fdf["ipk"] / 4.0).clip(upper=1.0)

        # --- interest component: normalisasi tier raw (0/1/2) -> 0..1.
        # interest_raw (mentah) tetap disimpan apa adanya di kolom
        # feature_df; interest_score di sini adalah versi ternormalisasi
        # yang dipakai untuk final_score & ditampilkan ke user.
        df["interest_score"] = fdf["interest_raw"] / MINAT_INDUSTRI_TIER_MAX

        # --- location / placement_preference: sudah 0..1 tunggal ---
        df["location_score"] = fdf["location_score"]
        df["placement_preference_score"] = fdf["placement_preference_score"]

        self._component_cache[tid] = df
        return df

    # -----------------------------------------------------------------
    # Final score (REAL-TIME, dipanggil ulang setiap slider bobot berubah)
    # -----------------------------------------------------------------
    def calculate_final_score(self, component_df: pd.DataFrame, weights: Optional[dict[str, float]] = None
                               ) -> pd.DataFrame:
        """
        Hanya menghitung ulang Final Matching Score dari component score
        yang sudah tersedia. TIDAK melakukan preprocessing / filtering /
        matching ulang.
        """
        if component_df.empty:
            out = component_df.copy()
            out["final_score"] = pd.Series(dtype=float)
            return out

        w = {**self.weights, **(weights or {})}
        wsum = sum(abs(v) for v in w.values()) or 1.0

        out = component_df.copy()
        out["final_score"] = (
            w.get("tool_match", 0.0) * out["tool_score"]
            + w.get("program_study", 0.0) * out["program_study_score"]
            + w.get("ipk", 0.0) * out["ipk_score"]
            + w.get("interest", 0.0) * out["interest_score"]
            + w.get("location", 0.0) * out["location_score"]
            + w.get("placement_preference", 0.0) * out["placement_preference_score"]
        ) / wsum
        return out

    def _compute_final_score(self, talent_request_id: str, weights: Optional[dict[str, float]] = None
                              ) -> pd.DataFrame:
        components = self.calculate_component_scores(talent_request_id)
        return self.calculate_final_score(components, weights)

    # -----------------------------------------------------------------
    # recommend() -- orkestrasi pipeline lengkap (TIDAK diubah)
    # -----------------------------------------------------------------
    def recommend(self, talent_request_id: str, top_n: Optional[int] = None,
                  weights: Optional[dict[str, float]] = None) -> pd.DataFrame:
        """
        Pipeline lengkap: filter -> match -> score -> rank -> top-N.

        Parameters
        ----------
        talent_request_id : id talent request.
        top_n : jumlah kandidat teratas. Boleh None/kosong -> kembalikan
            SELURUH kandidat eligible (diproses per-batch 100 baris
            mahasiswa untuk efisiensi, lihat `self.batch_size`).
        weights : override bobot 6 komponen secara real-time (tanpa
            memicu preprocessing/filtering/matching ulang).

        Returns
        -------
        DataFrame terurut (Ranking, NIM, Nama Mahasiswa, Program Studi,
        Final Score, Total Skor (Dinormalisasi), Tool Score, Program Study
        Score, IPK Score, Interest Score, Location Score, Placement
        Preference Score, Coverage Tools, Coverage Requirement, Confidence,
        Eligibility Status, Matched Tools, Suggested Tools, Jenis Tools
        Match, Semua Tools, IPK, Semester, Bidang Minat, Jenis Penempatan
        Diminati, CV, Portofolio, Punya Portofolio, Domisili, Status,
        Ketersediaan, Tools Cocok, Request Lain, Jumlah Request Lain,
        Alasan, ...). "Final Score" adalah skor absolut/mentah (dipakai
        untuk KPI skor tertinggi/rata-rata); "Total Skor (Dinormalisasi)"
        adalah skor min-max 0..100 dalam pool eligible request ini, dipakai
        untuk membandingkan kandidat satu sama lain di tabel dashboard.
        """
        if not self._initialized:
            raise RuntimeError("Engine belum di-initialize(). Panggil engine.initialize() terlebih dahulu.")

        tid = str(talent_request_id)
        logger.info("Loading candidate pool untuk %s", tid)
        candidates = self.filter_candidates(tid)

        logger.info("Eligible candidate pool: %d mahasiswa", len(candidates))
        self.match(tid, candidates, top_n=top_n)

        logger.info("Ranking kandidat")
        scored = self._compute_final_score(tid, weights)
        if scored.empty:
            return scored

        ranked = scored.sort_values("final_score", ascending=False).reset_index(drop=True)

        # Min-max final_score dihitung dari SELURUH kandidat eligible (ranked
        # utuh, sebelum top_n memotong baris) -- top_n cuma menentukan berapa
        # baris teratas yang ditampilkan, bukan rentang normalisasi.
        fs_all = ranked["final_score"]
        if fs_all.max() == fs_all.min():
            ranked["final_score_norm"] = 0.0
        else:
            ranked["final_score_norm"] = (fs_all - fs_all.min()) / (fs_all.max() - fs_all.min()) * 100

        if top_n:
            ranked = ranked.head(int(top_n))

        result = self._format_output(tid, ranked)
        logger.info("Recommendation generated: %d kandidat untuk %s", len(result), tid)
        return result

    @staticmethod
    def _tools_match_kind(matched: Optional[list], matched_suggested: Optional[list]) -> str:
        """Klasifikasi asal tools yang cocok untuk kolom "Jenis Tools Match".

        "Eksplisit" -- seluruh tools cocok disebut langsung di teks
        requirement. "Implisit" -- seluruh tools cocok berasal dari
        historical rule (lihat _infer_suggested_tools), tidak disebut
        eksplisit di requirement. "Campuran" -- gabungan keduanya. "-" --
        tidak ada tools yang cocok sama sekali. matched_suggested SELALU
        subset dari matched (lihat _match_tools), jadi matched kosong
        berarti matched_suggested juga kosong.
        """
        matched_set = set(matched or [])
        if not matched_set:
            return "-"
        suggested_set = set(matched_suggested or [])
        explicit_only = matched_set - suggested_set
        if explicit_only and suggested_set:
            return "Campuran"
        if suggested_set:
            return "Implisit"
        return "Eksplisit"

    def _format_output(self, talent_request_id: str, ranked: pd.DataFrame) -> pd.DataFrame:
        tid = str(talent_request_id)
        out = pd.DataFrame()
        out["Ranking"] = range(1, len(ranked) + 1)
        out["NIM"] = ranked["NIM"].values
        out["Nama Mahasiswa"] = [self._stu_name.get(n, "") for n in ranked["NIM"]]
        out["Program Studi"] = [self._stu_prodi_display.get(n, "") for n in ranked["NIM"]]
        out["Final Score"] = (ranked["final_score"] * 100).round(2).values
        # Skor total ternormalisasi (min-max 0..100 dalam pool eligible
        # request ini, lihat recommend()) -- inilah skor utama yang
        # dipakai untuk MEMBANDINGKAN kandidat satu sama lain di tabel
        # dashboard. "Final Score" (di atas) adalah skor absolut/mentah,
        # tetap disimpan untuk konteks & KPI (skor tertinggi/rata-rata).
        out["Total Skor (Dinormalisasi)"] = ranked["final_score_norm"].round(2).values
        out["Tool Score"] = (ranked["tool_score"] * 100).round(2).values
        out["Program Study Score"] = (ranked["program_study_score"] * 100).round(2).values
        out["IPK Score"] = (ranked["ipk_score"] * 100).round(2).values
        out["Interest Score"] = (ranked["interest_score"] * 100).round(2).values
        out["Location Score"] = (ranked["location_score"] * 100).round(2).values
        out["Placement Preference Score"] = (ranked["placement_preference_score"] * 100).round(2).values
        out["Coverage Tools"] = (ranked["tool_coverage"] * 100).round(1).values
        out["Coverage Requirement"] = (ranked["req_semantic"] * 100).round(1).values
        # Confidence: kelengkapan bukti pendukung profil (CV & portofolio)
        out["Confidence"] = ((ranked["has_cv"] + ranked["has_porto"]) / 2 * 100).round(1).values
        out["Eligibility Status"] = np.where(ranked["semester_ok"] > 0, "Eligible", "Eligible (cek semester)")
        out["Matched Tools"] = [", ".join(t) if t else "" for t in ranked["matched_tools"]]
        out["Suggested Tools"] = [", ".join(t) if t else "" for t in ranked["matched_suggested_tools"]]
        out["Jenis Tools Match"] = [
            self._tools_match_kind(t, s)
            for t, s in zip(ranked["matched_tools"], ranked["matched_suggested_tools"])
        ]
        out["Semua Tools"] = [
            ", ".join(sorted(self._stu_tools.get(n, set()))) for n in ranked["NIM"]
        ]
        out["IPK"] = ranked["ipk"].round(2).values
        out["Semester"] = [self._stu_sem.get(n, np.nan) for n in ranked["NIM"]]
        out["Bidang Minat"] = [self._stu_minat.get(n, "") for n in ranked["NIM"]]
        out["Jenis Penempatan Diminati"] = [
            self._stu_jenis_diminati.get(n, "") for n in ranked["NIM"]
        ]
        out["CV"] = [self._stu_cv.get(n, "") for n in ranked["NIM"]]
        out["Portofolio"] = [self._stu_porto.get(n, "") for n in ranked["NIM"]]
        out["Punya Portofolio"] = ranked["has_porto"].astype(bool).values
        out["Domisili"] = [self._stu_domisili.get(n, "") for n in ranked["NIM"]]
        # Perbandingan literal domisili vs kota kantor -- TIDAK memakai
        # location_score (yang dilonggarkan/dinetralkan untuk WFH/Hybrid,
        # lihat _match_location). Dipakai untuk KPI pie chart "domisili
        # sama dengan kantor" di dashboard, bukan komponen skor.
        kota_kantor = self._req_kota_by_tid.get(tid, "")
        kota_kantor_norm = self._normalize_text(kota_kantor)
        out["Domisili Sama Kantor"] = [
            bool(kota_kantor_norm) and not pd.isna(d) and self._normalize_text(d) == kota_kantor_norm
            for d in out["Domisili"]
        ]
        out["Status"] = [self._stu_status.get(n, "") for n in ranked["NIM"]]
        out["Ketersediaan"] = [self._stu_avail.get(n, "") for n in ranked["NIM"]]
        out["Tools Cocok"] = ranked["tool_count"].astype(int).values
        out["Request Lain"] = [
            self.other_request_label(n, exclude_tid=tid) for n in ranked["NIM"]
        ]
        out["Jumlah Request Lain"] = [
            self.other_request_count(n, exclude_tid=tid) for n in ranked["NIM"]
        ]
        out["Alasan"] = [self.explain(talent_request_id, n, feature_row=row) for n, (_, row) in
                          zip(ranked["NIM"], ranked.iterrows())]
        out.index = out["Ranking"]
        return out

    # -----------------------------------------------------------------
    # Explainability
    # -----------------------------------------------------------------
    def explain(self, talent_request_id: str, nim: str, feature_row: Optional[pd.Series] = None) -> str:
        """
        Hasilkan alasan human-readable mengapa seorang kandidat
        direkomendasikan (otomatis dari hasil scoring, seluruh fitur baru
        termasuk).
        """
        tid = str(talent_request_id)
        if feature_row is None:
            components = self.calculate_component_scores(tid)
            match_row = components[components["NIM"] == str(nim)]
            if match_row.empty:
                return "Kandidat tidak ditemukan pada hasil matching untuk talent request ini."
            feature_row = match_row.iloc[0]

        f = feature_row
        parts: list[str] = []
        if f["prodi_exact"] > 0:
            parts.append("program studi sesuai")
        elif f["prodi_semantic"] >= self.thresholds["prodi_semantic_min"]:
            parts.append(f"prodi mirip (sim={f['prodi_semantic']:.2f})")

        matched = f.get("matched_tools") or []
        if matched:
            parts.append("tools yang cocok adalah " + ", ".join(matched))
        suggested = f.get("matched_suggested_tools") or []
        if suggested:
            parts.append(
                ", ".join(suggested) + " sebagai implicit tools hasil historical rule"
            )

        if f["req_semantic"] >= self.thresholds["req_semantic_min"]:
            parts.append(f"requirement memiliki kecocokan tinggi (sim={f['req_semantic']:.2f})")

        interest_raw = f.get("interest_raw", 0)
        industri = self._req_industri_by_tid.get(tid, "")
        if interest_raw >= 2:
            parts.append(
                f"bidang minat sangat sesuai dengan sektor industri {industri}" if industri
                else "bidang minat sangat sesuai dengan sektor industri perusahaan"
            )
        elif interest_raw >= 1:
            parts.append(
                f"bidang minat cukup relevan dengan sektor industri {industri}" if industri
                else "bidang minat cukup relevan dengan sektor industri perusahaan"
            )

        loc = f.get("location_score", 0)
        if loc >= 1.0:
            parts.append("domisili sesuai dengan lokasi penempatan")
        elif loc >= 0.5:
            parts.append("domisili cukup dekat dengan lokasi penempatan")

        if f.get("placement_preference_score", 0) >= 1.0:
            parts.append("preferensi jenis penempatan sesuai")

        if f["has_cv"] > 0:
            parts.append("punya CV")
        if f["has_porto"] > 0:
            parts.append("punya portofolio")
        if f["ipk"] > 0:
            parts.append(f"IPK {f['ipk']:.2f}")

        if "final_score" in f:
            parts.append(f"final score {f['final_score']*100:.2f}")

        return "Kandidat direkomendasikan karena: " + "; ".join(parts) if parts else "Kecocokan lemah."

    # -----------------------------------------------------------------
    # Cache management (TIDAK diubah)
    # -----------------------------------------------------------------
    def clear_cache(self, talent_request_id: Optional[str] = None) -> None:
        """
        Bersihkan cache matching (feature/component/candidate) bila data
        berubah. Precompute dasar (lexicon, historical dict) TIDAK ikut
        dihapus -- panggil `initialize(force=True)` bila data mentah
        berubah total.
        """
        if talent_request_id is None:
            self._candidate_cache.clear()
            self._feature_cache.clear()
            self._component_cache.clear()
            logger.info("Seluruh cache matching dibersihkan.")
        else:
            tid = str(talent_request_id)
            self._candidate_cache.pop(tid, None)
            self._feature_cache.pop(tid, None)
            self._component_cache.pop(tid, None)
            logger.info("Cache matching untuk %s dibersihkan.", tid)

    # -----------------------------------------------------------------
    # Utilities untuk dashboard
    # -----------------------------------------------------------------
    def list_talent_requests(self) -> pd.DataFrame:
        """Daftar talent request beserta info ringkas, untuk dropdown Streamlit."""
        if self.talent_req_df is None:
            raise RuntimeError("Engine belum di-initialize().")
        cols = [c for c in [
            self._t_id_col,
            self._get_col(self.talent_req_df, "t_position", "talent_request"),
            self._get_col(self.talent_req_df, "t_company_name", "talent_request"),
            self._get_col(self.talent_req_df, "t_min_sem", "talent_request"),
            self._get_col(self.talent_req_df, "t_headcount", "talent_request"),
        ] if c]
        return self.talent_req_df[cols].copy()

    def get_talent_request_detail(self, talent_request_id: str) -> dict:
        tid = str(talent_request_id)
        if tid not in self._req_full_by_tid:
            raise KeyError(f"Talent request '{tid}' tidak ditemukan.")
        return {
            "id": tid,
            "position": self._req_position_by_tid.get(tid, ""),
            "bidang": self._req_bidang_by_tid.get(tid, []),
            "required_tools": self._req_tools_by_tid.get(tid, []),
            "explicit_tools": self._req_explicit_tools_by_tid.get(tid, []),
            "suggested_tools": self._req_suggested_tools_by_tid.get(tid, []),
            "minimum_semester": self._req_minsem_by_tid.get(tid, None),
            "working_arrangement": self._req_wa_by_tid.get(tid, ""),
            "kota_kantor": self._req_kota_by_tid.get(tid, ""),
            "jenis_penempatan": self._req_jenis_by_tid.get(tid, ""),
            "industri_sektor": self._req_industri_by_tid.get(tid, ""),
        }


# =====================================================================
# Dashboard helpers -- consumed by pages/2_Matching.py. Plain functions,
# no Streamlit/session-state coupling, so the page itself stays UI-only
# (widgets, layout, session state): pages never own business/data logic.
# =====================================================================

def stringify(value: Any) -> str:
    """Render any cell value (list/set/NaN/scalar) as display text."""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(map(str, value))
    if pd.isna(value):
        return ""
    return str(value)


def split_list_value(value: Any) -> list[str]:
    """Split a multi-value cell (list, or comma/semicolon delimited string) into clean tokens."""
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if pd.isna(value):
        return []
    return [
        item.strip().strip("[]'\"")
        for item in str(value).replace(";", ",").split(",")
        if item.strip().strip("[]'\"")
    ]


def unique_sorted_values(series: pd.Series) -> list[str]:
    """Unique, sorted string values from a series that may hold multi-value cells."""
    values = []
    for value in series.dropna():
        if isinstance(value, (list, tuple, set)):
            values.extend(split_list_value(value))
        else:
            values.append(str(value).strip())
    return sorted({value for value in values if value})


def numeric_or_zero(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def candidate_id_column(df: pd.DataFrame) -> str:
    for col in ["NIM", "nim", "id_status", "id_student", "email"]:
        if col in df.columns:
            return col
    return df.columns[0]


def csv_download_bytes(df: pd.DataFrame) -> bytes:
    """Encode a dataframe as UTF-8-BOM CSV bytes, ready for st.download_button."""
    out = df.copy()

    def normalize_cell(value):
        if isinstance(value, (list, tuple, set)):
            return ", ".join(map(str, value))
        return value

    for col in out.columns:
        out[col] = out[col].map(normalize_cell)
    return out.to_csv(index=False).encode("utf-8-sig")


def request_export_frame(req: pd.Series, tr_req: pd.Series, co_req: pd.Series) -> pd.DataFrame:
    """One-row export frame combining a tracking_company/talent_request/company record."""
    return pd.concat(
        [
            req.to_frame().T.reset_index(drop=True).add_prefix("tracking_"),
            tr_req.to_frame().T.reset_index(drop=True).add_prefix("request_"),
            co_req.to_frame().T.reset_index(drop=True).add_prefix("company_"),
        ],
        axis=1,
    )


def request_headcount_column(df: pd.DataFrame) -> Optional[str]:
    for col in ["headcount", "jumlah_permintaan", "jumlah_dibutuhkan"]:
        if col in df.columns:
            return col
    return None


def build_request_filter_frame(draft_req: pd.DataFrame, talent_request: pd.DataFrame) -> pd.DataFrame:
    """Add a numeric headcount_filter column to the draft-request table for the sidebar filters."""
    out = draft_req.copy()
    if "headcount" not in out.columns and {"id_talent_req", "headcount"}.issubset(talent_request.columns):
        out = out.merge(
            talent_request[["id_talent_req", "headcount"]],
            on="id_talent_req",
            how="left",
        )

    headcount_col = request_headcount_column(out)
    if headcount_col is None:
        out["headcount_filter"] = 0
    else:
        out["headcount_filter"] = numeric_or_zero(out[headcount_col])
    return out


def resolve_headcount_range(min_text: Any, max_text: Any, dataset_min: int, dataset_max: int) -> tuple[int, int]:
    """Parse the two headcount text inputs into a clamped (lo, hi) range.

    Empty or unparseable input falls back to the dataset bound on that
    side. Values outside [dataset_min, dataset_max] are clamped. A
    reversed entry (min text > max text) is swapped, so the range filter
    downstream never sees an impossible bound.
    """
    def parse_bound(text_value, fallback):
        text_value = str(text_value).strip()
        if not text_value:
            return fallback
        try:
            return int(float(text_value))
        except ValueError:
            return fallback

    lo = parse_bound(min_text, dataset_min)
    hi = parse_bound(max_text, dataset_max)
    lo = max(dataset_min, min(lo, dataset_max))
    hi = max(dataset_min, min(hi, dataset_max))
    return (lo, hi) if lo <= hi else (hi, lo)


def requested_program_options(req: pd.Series) -> list[str]:
    values = split_list_value(req.get("bidang_studi_dicari_list", ""))
    if not values:
        values = split_list_value(req.get("bidang_studi_dicari", ""))
    return values


def candidate_display_columns(df: pd.DataFrame) -> list[str]:
    """Preferred, ordered subset of MatchingEngine.recommend() columns for the candidate table."""
    preferred = [
        "NIM", "Nama Mahasiswa", "Program Studi", "IPK", "Final Score",
        "Total Skor (Dinormalisasi)", "Matched Tools", "Jenis Tools Match",
        "Semester", "Bidang Minat", "Jenis Penempatan Diminati", "CV",
        "Portofolio", "Domisili", "Status", "Ketersediaan", "Semua Tools",
        "Request Lain", "Jumlah Request Lain",
    ]
    return [col for col in preferred if col in df.columns]


def highlight_candidate_status(row: pd.Series) -> list[str]:
    """Row style function for st.DataFrame.style.apply: color-codes Jenis Tools Match & Request Lain."""
    warna = config.WARNA
    styles = [""] * len(row)
    for idx, col in enumerate(row.index):
        if col == "Jenis Tools Match":
            value = stringify(row[col]).lower()
            if "campuran" in value:
                styles[idx] = f"background-color: {warna['hot_bg']}; color: {warna['hot']};"
            elif "implisit" in value:
                styles[idx] = f"background-color: {warna['watch_bg']}; color: {warna['watch']};"
            elif "eksplisit" in value:
                styles[idx] = f"background-color: {warna['ok_bg']}; color: {warna['ok']};"
        if col == "Request Lain":
            value = stringify(row[col]).lower()
            if "tidak" in value:
                styles[idx] = f"background-color: {warna['ok_bg']}; color: {warna['ok']};"
            else:
                styles[idx] = f"background-color: {warna['watch_bg']}; color: {warna['watch']};"
    return styles
