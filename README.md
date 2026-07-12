# SSDC Dashboard — Team Guideline

Streamlit dashboard for the Student Placement System (SSDC) dataset.
6 tables, 79 columns, ~18MB total.

**Read this before writing any code.**

---

## 1. Phase 0 — Data Profiling (before the first meeting)

We work in parallel from day one. Each person takes a **cluster** of related tables — not one CSV each, because the interesting problems live *between* tables.

| Person | Cluster | Files |
|---|---|---|
| A | Company side | `company.csv`, `talent_request.csv` |
| B | Student side | `student_all.csv`, `status_student.csv` |
| C | Tracking side | `tracking_company.csv`, `tracking_student.csv` |

C's cluster is the messiest — give it to whoever has the most bandwidth.

### What to check per cluster

**A — Company side**
- Does every `talent_request.id_company` exist in `company`? Count orphans.
- Is `nama_perusahaan` (talent_request) consistent with `company.company_name`?
- Are `headcount` and `minimum_semester` clean integers?
- Value counts for: `jenis_penempatan`, `working_arrangement`, `industri_sektor`, `company_type`, `skala_perusahaan`, `sumber_baris_form`.

**B — Student side**
- Is `nim` truly 1:1 between the two tables? Anyone in one but not the other?
- Is `ipk` numeric and within a plausible range?
- Does `semester` agree between `student_all` and `status_student`?
- Value counts for: `status`, `ketersediaan`, `cv`, `portofolio`, `program_studi`, `bidang_minat`, `jenis_penempatan_diminati`.
- Parse `tools` (comma-separated) — how many distinct tools, how dirty are they?

**C — Tracking side**
- Explode `list_nim` and reconcile against `tracking_student` rows. Do they match?
- Does `jumlah_dikirimkan` equal the actual count in `list_nim`?
- Do `progress_student` and `rejection` ever contradict each other?
- Orphan FKs: `id_talent_req`, `id_company`, `nim`, `id_tracking_company`.
- Value counts for: `progress`, `progress_student`, `rejection`.

### Deliverable — same format for everyone

One notebook per cluster, plus append your section to the shared findings doc:

```
## Findings — <cluster>

Rows / dtypes / nulls per column
Categorical columns: FULL value_counts   <- the most important artifact
FK integrity: X orphans out of Y
Duplicates: found / not found

Open questions for the meeting:
- ...
```

The `value_counts` of every categorical is the highest-value thing you will produce.
Whether `jenis_penempatan` is `{Magang, Part-time, Full-time}` or
`{Magang, magang, MAGANG, Intern, ...}` changes everything downstream.

---

## 2. Phase 0 — Do / Don't

### DO
- Profile, document, write findings.
- Fix only **obvious within-cluster** issues: strip whitespace, normalize case, cast dtypes.
- Log every assumption you make.
- Write unresolved issues under "Open questions" and **keep moving**.
- Look at `tracking_company.list_nim` early — all three of you. It's the join that holds
  the whole dashboard together.

### DON'T
- Don't invent business logic. ("Inactive students shouldn't count in the funnel" is a
  **meeting decision**, not a Phase-0 decision.)
- Don't build a matching score yet.
- Don't merge tables outside your cluster.
- Don't decide funnel stages, KPI definitions, or ghosting thresholds alone.
- Don't block waiting for an answer — write the question down and continue.
- Don't touch `app.py` yet. It doesn't exist.

Rationale: if three people make business-logic decisions independently, Day 3 gets spent
undoing two of the three versions.

---

## 3. After the meeting — Layer split

We split by **layer**, not by page. Splitting by page means three people re-reading the
same CSVs, three color palettes, and a merge conflict on `app.py` every commit.

| Person | Layer | Owns |
|---|---|---|
| A | Data & Metrics | `data/`, `metrics/` — loaders, joins, cached. **Only A touches raw CSVs.** |
| B | Analytics & Charts | `charts/` — funnel, matching score, ghosting detector, cohort analysis |
| C | App Shell & UX | `app.py`, `pages/`, `components/` — theme, filters, layout, KPI cards |

**Contract between layers = function signatures.** Agree on them in the first 2 hours of
the meeting, stub with fake data, then go parallel.

```python
# metrics/api.py — owned by A, consumed by B and C
load_all()                                  -> dict[str, pd.DataFrame]   # cached
get_funnel(filters)                         -> pd.DataFrame
get_placement_rate(filters)                 -> float
get_ghosting_candidates(filters)            -> pd.DataFrame
get_matching_scores(nim, id_talent_req)     -> float
```

Every number in the dashboard comes from `metrics/`. That's how definitions stay consistent.

**Freeze the API at the end of the meeting.** If it changes on Day 4, we lose Day 4.

---

## 4. Planned pages

| Page | Covers |
|---|---|
| Overview | Funnel Request → Sent → Interview → Placement, headline KPIs (BT-04, BT-07) |
| Matching | Pick a talent request → ranked eligible students with transparent score (BT-01, BT-06) |
| Pipeline Monitor | Per-student progress, stuck / aging records (BT-02, BT-03) |
| Ghosting & Follow-up | Alert board for non-responders (BT-05) |
| Reports | Placement rate by prodi / company / jenis_penempatan (BT-07) |

Maps ~1:1 to the business tasks in the dataset documentation. Keep it that way.

---

## 5. Known data gotchas

- **`list_nim` is a comma-separated TEXT blob** in `tracking_company`. It is the bridge
  between the company side and the student side. Explode it early.
- **`jumlah_dikirimkan` can exceed `jumlah_permintaan`** (buffer). Don't naively compute fill rate.
- **`progress_student` and `rejection` overlap.** Decide which is canonical for the funnel
  *before* building charts, or you'll build it twice.
- **Heavy denormalization** — `nama_perusahaan` appears in 3 tables. Treat
  `company.company_name` as truth; inconsistencies elsewhere are a **finding**, not a bug to hide.
- **Files are small** (max 4.8MB). `@st.cache_data` on a single load is enough. No database.

---

## 6. Repo conventions

- One repo, one branch per person, **C merges**.
- Raw CSVs go in `data/raw/` and are **never edited in place**.
- Cleaning happens in code, not in Excel. Every transformation must be reproducible.
- Add data files to `.gitignore` if they're large or private — commit the loader, not the data.
- Commit messages: `[A] add company loader`, `[B] funnel chart`, `[C] sidebar filters`.

## 7. Structure (post-meeting)

```
.
├── app.py                 # C
├── data/
│   ├── raw/               # the 6 CSVs, read-only
│   └── loaders.py         # A
├── metrics/
│   └── api.py             # A  — the contract
├── charts/                # B
├── components/            # C
├── pages/                 # C
└── notebooks/
    ├── profiling_company.ipynb    # A, phase 0
    ├── profiling_student.ipynb    # B, phase 0
    └── profiling_tracking.ipynb   # C, phase 0
```

---

## 8. Timeline

| Phase | A | B | C |
|---|---|---|---|
| Day 1–2 | Profile company cluster | Profile student cluster | Profile tracking cluster |
| Meeting | **Together:** review findings, resolve open questions, freeze the API, lock metric definitions |
| Day 3–4 | Loaders, joins | Funnel + matching algo | Shell, theme, filters, mock pages |
| Day 5–6 | Metric functions | Charts, remaining analyses | Wire real data, polish |
| Final | **Together:** cut dead pages, write the narrative, rehearse the demo |