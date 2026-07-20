# SPESIFIKASI TEKNIS DASHBOARD SSDC
## Kamus Metrik, Aturan Pembersihan Data, dan Rancangan Halaman

**Tim:** Andalan (Analitik), Mutia (Matching), Afrizal (Monitoring). Beranda dikerjakan terakhir oleh siapa pun yang selesai lebih dulu.
**Status dokumen:** SEMUA definisi di dokumen ini sudah FINAL dan disepakati tim, kecuali bagian yang ditandai `[OWNER-DECIDED]`.

---

## BAGIAN 0 — CARA MEMBACA DOKUMEN INI

Dokumen ini adalah **satu-satunya sumber kebenaran** untuk membangun dashboard Streamlit SSDC. Pembaca utamanya adalah anggota tim, dan boleh diberikan ke LLM sebagai referensi penulisan kode Python. Aturan membaca:

1. Nama kolom ditulis `monospace` (contoh: `progress_student`). Nilai kategori ditulis dengan kutip (contoh: `'Placement'`). Keduanya **case-sensitive** — jangan pernah menulis `'placement'` atau `'PLACEMENT'`.
2. Setiap metrik HANYA boleh didefinisikan di `core/metrics.py`. Halaman (`pages/`) HANYA memanggil fungsi dari `core/`, tidak pernah menulis ulang rumus seperti `df['rejection']=='Placement'` secara langsung.
3. Tanda `[OWNER-DECIDED: nama]` berarti detail tersebut ditentukan oleh anggota tim pemilik halaman saat implementasi. Builder tetap membangun **kerangkanya** sesuai usulan yang tertulis, dengan komentar `# TODO(owner)` di kode.
4. Tanda `[HITUNG-ULANG]` berarti angka di mockup lama SUDAH TIDAK BERLAKU dan harus dihitung ulang dari data memakai definisi final di dokumen ini.
5. Bagian 10 berisi **checklist verifikasi** — angka-angka yang HARUS keluar persis sama saat builder menjalankan pipeline. Jika ada yang meleset, ada bug di loader/cleaner/metrics; berhenti dan perbaiki sebelum lanjut.
6. Dashboard bersifat **read-only** terhadap CSV. Tidak ada tulisan balik ke file data. Satu-satunya "state" adalah `st.session_state` (hilang saat refresh).

### Konteks singkat

Dashboard ini untuk lomba visualisasi data. Skenario: Career Development Center (CDC) kampus menyalurkan mahasiswa ke perusahaan mitra (magang/part-time/full-time). Ada 8 business task resmi (BT-01 s.d. BT-08, dirinci di Bagian 6). Filosofi desain tim: **operational-first** — dashboard adalah alat kerja CDC (antrean tindakan, matching, monitoring), dengan **analitik sebagai pendukung pelaporan**. Pembeda utama tim: **drill-down level individu** di halaman Beranda.

---

## BAGIAN 1 — DATASET & RELASI

Data mentah ada di folder `Data/Raw/` (relatif terhadap root repo). Dashboard dibangun di folder baru `dashboard/` (lihat Bagian 7).

| File | Baris | Kolom | Delimiter | Catatan |
|---|---|---|---|---|
| `company.csv` | 1.500 | 9 | koma | Master perusahaan mitra |
| `talent_request.csv` | 12.000 | 19 | koma | Permintaan talent per posisi |
| `student_all.csv` | 25.000 | 10 | koma | Master mahasiswa (statis) |
| `status_student.csv` | 25.000 | 15 | **TITIK-KOMA (`;`)** | Status dinamis mahasiswa. Dokumentasi panitia menulis 16 kolom; panitia konfirmasi kolom "eligible" = kolom `ketersediaan`, jadi 15 memang lengkap |
| `tracking_company.csv` | 12.000 | 13 | koma | Rekap pengiriman per request. Dokumentasi menulis 14 kolom; panitia konfirmasi itu salah tulis, 13 yang benar |
| `tracking_student.csv` | 41.600 | 11 | koma | Detail proses seleksi per mahasiswa per perusahaan — **tabel terpenting** |

**PERHATIAN — versi file tracking_company.** Di `Data/Raw/` ada tiga file: `tracking_company.csv`, `tracking_company_new.csv`, `tracking_company_old.csv`. Latar: panitia pernah mengumumkan perbaikan `list_nim`, tetapi file "baru" terbukti identik byte-per-byte dengan yang lama (checksum sama). **Instruksi builder:** verifikasi checksum ketiganya saat setup; gunakan `tracking_company.csv` sebagai default. Perbaikan 48 baris `list_nim` rusak dilakukan di kode (Bagian 3.4), BUKAN dengan mengedit CSV.

### Relasi antar tabel

```
company (id_company)
   │ 1:N
   ▼
talent_request (id_talent_req, FK id_company)
   │ 1:1  ← di data ini pemetaannya tepat 1:1 (12.000 ↔ 12.000)
   ▼
tracking_company (id_tracking_company, FK id_talent_req, FK id_company)
   │ 1:N
   ▼
tracking_student (id_tracking_student, FK id_tracking_company, FK NIM)
   ▲
   │ N:1
student_all (NIM) ──1:1── status_student (FK NIM, UNIQUE)
```

Integritas referensial **sempurna**: 0 orphan di semua FK (sudah diverifikasi tim). Semua 12.000 `id_talent_req` muncul di tracking_company dan sebaliknya. Setiap NIM di status_student & tracking_student ada di student_all. Setiap NIM student_all punya tepat satu baris status_student.

### Fakta kunci tentang isi data

- 10.174 NIM unik pernah dikirim (muncul di tracking_student); 8.845 di antaranya (87%) dikirim ke >1 perusahaan (maks 19).
- Nama TIDAK unik: hanya 5.665 nama unik dari 25.000 mahasiswa. Email juga tidak unik. **Semua join dan hitung unik WAJIB berbasis `NIM`.**
- `bidang_studi_dibutuhkan` (talent_request) berisi kombinasi comma-separated dari 18 nilai prodi yang sama persis dengan `program_studi` mahasiswa (closed set — lihat Bagian 5.4). 86% request mencantumkan >1 prodi.
- `status_student.tools`: comma-separated, terisi di seluruh 25.000 baris, median 4 tools/mahasiswa.
- `tracking_company.list_nim`: comma-separated NIM; isinya konsisten dengan baris tracking_student (kecuali 48 baris rusak — Bagian 3.4).

---

## BAGIAN 2 — ATURAN PEMUATAN DATA (`core/loader.py`)

### 2.1 Aturan dtype WAJIB, pelanggaran = bug

| Kolom | File | dtype | Alasan |
|---|---|---|---|
| `NIM` | semua file yang memuatnya | `str` | pandas default membacanya int64; perbandingan int vs str membuat join gagal diam-diam |
| `hp` | student_all | `str` | leading zero (format 08xx) hilang jika dibaca angka |
| `no_whatsapp` | status_student, talent_request | `str` | sama; khusus status_student leading zero SUDAH hilang di sumber (Bagian 3.6) |
| `pic_phone` | company | `str` | sama |
| `IPK` | status_student | `float` | desimal titik |
| `headcount`, `minimum_semester`, `semester`, `jumlah_permintaan`, `jumlah_dikirimkan`, `internship_semester` | masing-masing | numerik (`Int64` nullable aman) | |
| semua ID (`id_company`, `id_talent_req`, `id_tracking_company`, `id_tracking_student`, `id_status`) | masing-masing | `str` | |

Implementasi: `pd.read_csv(..., dtype={...})` dengan dict eksplisit per file. Untuk status_student: `pd.read_csv(path, sep=';', dtype={...})` lalu `df.columns = [c.strip() for c in df.columns]` (nama kolom bisa berspasi).

### 2.2 Format tanggal — parse per kolom, JANGAN pakai satu format global

| Kolom | File | Format | Sudah diverifikasi? |
|---|---|---|---|
| `request_date`, `send_date` | tracking_company | `%d/%m/%Y` | Ya |
| `last_update` | tracking_student | `%Y-%m-%d` | Ya |
| `sync_date` | status_student | `%d/%m/%Y` | Ya |
| `request_date` | talent_request | verifikasi saat load | Belum dicek eksplisit — parse dengan kedua format, pilih yang `notna()` > 95% |
| `created_at` | company | bebas (kolom ini DIABAIKAN — Bagian 3.8) | — |

**Wajib assert setelah parse:** `parsed.notna().mean() > 0.95` untuk kolom tanggal non-nullable. Pengecualian: `send_date` di tracking_company punya **598 nilai kosong yang bermakna** (request berstatus `'Draft'`, belum dikirim) — jangan dianggap gagal parse.

### 2.3 Tanggal jangkar (anchor) — dihitung DINAMIS, dilarang hard-code

```python
ANCHOR = max(
    tracking_student['last_update'].max(),
    tracking_company['send_date'].max(),
    tracking_company['request_date'].max(),
    status_student['sync_date'].max(),
)
# Pada data saat ini hasilnya = 2025-05-17 (dari last_update)
```

- **JANGAN pakai `datetime.today()`** untuk perhitungan umur apa pun. Data ini snapshot beku; "hari ini" membuat semua umur membengkak >1 tahun dan merusak logika FU/ghosting.
- Semua "umur" proses = `ANCHOR − kolom_tanggal` dalam hari.
- Khusus BT-08 (kesegaran sync): slider umur sync dihitung relatif ke `SYNC_REF = status_student['sync_date'].max()` (= 2025-01-31 pada data ini), karena desain yang disepakati adalah "jumlah baris yang sync-nya X hari **sejak data terakhir yang di-sync**". Tampilkan juga info "data mahasiswa terakhir di-sync: {SYNC_REF}". `ANCHOR` global tetap 17 Mei untuk semua umur proses lainnya.
- Bukti kenapa anchor bukan `send_date.max()` (21 Feb 2025): 2.352 baris ter-update setelah tanggal itu → menghasilkan umur negatif. `ANCHOR` yang benar tidak menghasilkan satu pun umur negatif.

---

## BAGIAN 3 — ATURAN PEMBERSIHAN DATA (`core/clean.py`)

Setiap aturan: **kondisi → tindakan → alasan → referensi**. Prinsip umum: **flag, bukan drop** — baris bermasalah ditandai kolom boolean, tidak dihapus, supaya tetap bisa dilaporkan sebagai temuan kualitas data.

### 3.1 Anomali "Finish + On Progress"

- **Kondisi:** `(tracking_student.progress_student == 'Finish') & (tracking_student.rejection == 'On Progress')` → **2.578 baris**.
- **Tindakan:** tambah kolom `is_anomali = True` pada baris ini. JANGAN drop.
- **Alasan:** kedua nilai kontradiktif ("proses selesai" vs "masih berjalan"). Panitia secara resmi menyebutnya *noise/anomali data* dan menyerahkan penanganannya ke peserta.
- **Pemakaian:** setiap perhitungan **tingkat keberhasilan** (numerator dan denominator, di semua halaman dan semua periode) memakai `df[~df.is_anomali]`. Perhitungan lain (antrean, funnel tahap aktif) boleh memakai semua baris karena baris anomali ber-`progress 'Finish'` tidak masuk kategori aktif mana pun.
- **PENTING — jangan tertukar:** baris `'Finish'` + `rejection 'Placement'` (**1.421 baris**) BUKAN anomali. Itu placement sah yang prosesnya sudah diarsipkan, dan justru alasan tim memilih `rejection` sebagai definisi placement (Bagian 4.1).

### 3.2 Kolom `tracking_company.progress` — DILARANG untuk funnel

- **Temuan:** 75% baris `'Closed'` masih punya mahasiswa di tahap aktif; 94% baris `'Submitted'` anaknya justru sudah selesai. Kolom rekap ini tidak sinkron dengan detail.
- **Tindakan:** funnel dan semua agregat tahap dibangun HANYA dari `tracking_student`. `tracking_company.progress` hanya boleh dipakai untuk satu hal: mendeteksi request `'Draft'` (Bagian 4.8).

### 3.3 598 request Draft — null bermakna

- **Kondisi:** `tracking_company.send_date` kosong & `list_nim` kosong & `progress == 'Draft'` — 598 baris yang sama.
- **Tindakan:** JANGAN diimputasi. Ini "request masuk tapi belum digarap" — justru jadi KPI BT-03 di halaman Matching.

### 3.4 48 baris `list_nim` rusak

- **Kondisi:** `list_nim` berisi satu NIM sah diikuti `",2"` (contoh: `"20211268,2"`) — pemotongan angka oleh spreadsheet.
- **Tindakan:** rekonstruksi via kode: untuk tiap baris rusak, tracking_student selalu punya tepat satu baris tambahan dengan `id_tracking_company` sama yang NIM-nya hilang dari list. Buat kolom `list_nim_bersih`. CSV mentah TIDAK diedit. (Sudah terbukti seluruh 48 baris terekonstruksi tanpa ambiguitas — notebook `checking_tracking.ipynb`.)
- **Kebijakan:** `tracking_student` adalah **sumber kebenaran pengiriman per-NIM**; `list_nim` hanya referensi silang `jumlah_dikirimkan`.

### 3.5 NIM & join

- Paksa `str` di semua tabel (Bagian 2.1). Semua join pakai `NIM`. Dilarang join/dedup pakai nama atau email (tidak unik).

### 3.6 Nomor telepon

- `status_student.no_whatsapp` kehilangan awalan nol di SELURUH 25.000 baris (mulai `8xx...`). Kolom `student_all.hp` masih benar (mulai `08xx...`) dan angkanya identik.
- **Tindakan:** untuk kontak mahasiswa, pakai `student_all.hp` (join via NIM), ATAU perbaiki `no_whatsapp` dengan prefix `'0'`. Pilih satu, konsisten. Rekomendasi: pakai `hp`.
- Link WhatsApp: `https://wa.me/62{nomor_tanpa_nol_depan}`.

### 3.7 `bidang_studi_dibutuhkan` / `bidang_studi_dicari` multi-value

- **Tindakan:** parse jadi list: `[s.strip() for s in val.split(',')]`. Simpan sebagai kolom list (atau set) untuk pengecekan keanggotaan di Matching. **JANGAN explode permanen jadi baris.**

- **PERINGATAN.** Pernah dibuat file `Data/Cleaned/tracking_company_cleaned.csv` yang meng-explode `bidang_studi_dicari` jadi satu baris per prodi. Akibatnya baris naik 12.000 menjadi 22.284, `id_tracking_company` jadi tidak unik, dan file itu **merusak pipeline** jika dipakai sebagai sumber: join ke tracking_student menggembung 1,858x (41.600 menjadi 77.288), `jumlah_dikirimkan` ter-double-count 35.688, dan hitungan Draft naik palsu 598 menjadi 1.124. **Aturan final:** sumber tracking_company di dashboard SELALU `Data/Raw/tracking_company.csv` (12.000 baris). Bentuk explode hanya dibuat sebagai turunan di kode (`df.explode('bidang_studi_list')`) di tempat yang butuh tampilan per-prodi, TIDAK PERNAH sebagai file sumber yang di-load. Checklist Bagian 10 (cek #1 = 12.000 baris, cek #14 = 598 Draft) otomatis menolak file explode jika keliru masuk loader.

- **Catatan `list_nim`.** File cleaned tersebut juga memperbaiki 48 baris `list_nim` rusak. Perbaikannya sudah diverifikasi COCOK PERSIS dengan rekonstruksi Bagian 3.4 (himpunan NIM identik). Jadi tidak ada yang perlu diimpor: kode kita di `core/clean.py` sudah menghasilkan hasil yang sama, dan menyimpannya di kolom terpisah `list_nim_bersih` sambil mempertahankan kolom mentah untuk pelaporan kualitas data.

### 3.8 Aturan "catat saja, jangan bersihkan"

| Temuan | Keputusan |
|---|---|
| `request_date` < `created_at` pada 3.364 baris (28%) | Perilaku normal sistem (`created_at` = tanggal input, bukan tanggal berdiri relasi). **`created_at` DIABAIKAN sepenuhnya**; acuan waktu sisi perusahaan = `request_date` |
| PIC talent_request ≠ PIC company (40,5%) | Normal per dokumentasi. Pakai apa adanya |
| `jumlah_dikirimkan` > `jumlah_permintaan` (71,5%) | Buffer wajar. Catat di laporan, jangan "koreksi" |
| `internship_semester` identik dengan semester terkini di seluruh 41.600 baris | Bukan catatan historis. Rekap per periode WAJIB pakai kolom tanggal, bukan kolom ini |
| 5 perusahaan tak pernah request | Wajar, catat |
| `Data/Cleaned/tracking_company_cleaned.csv` (buatan tim) | JANGAN dipakai sebagai sumber. Ini versi ter-explode yang merusak join. Sumber tetap `Data/Raw/tracking_company.csv`. Lihat 3.7 |

---

## BAGIAN 4 — KAMUS METRIK (`core/metrics.py`) — INTI DOKUMEN

Setiap entri: fungsi → definisi → rumus pasti → edge case → alasan keputusan. Semua fungsi menerima dataframe hasil `loader`+`clean` dan mengembalikan nilai/mask/dataframe. Nilai kategori diambil dari konstanta `core/schema.py` (Bagian 5.1), bukan string literal.

### 4.1 Placement — DUA definisi untuk DUA konteks (keduanya resmi)

**(a) `is_placement_success(df)` — definisi KEBERHASILAN (BT-04, semua success rate):**

```python
mask = df['rejection'] == 'Placement'      # pada tracking_student
```

- Jumlah baris = **8.955**. NIM unik = **5.759**.
- **Alasan memilih `rejection`, bukan `progress_student`** (tulis ini di laporan): terdapat 1.421 baris `progress_student=='Finish'` dengan `rejection=='Placement'` — placement sah yang prosesnya telah diarsipkan. Kombinasi ini BUKAN anomali (kedua nilai konsisten: proses selesai, hasil berhasil). Memakai `progress_student` akan menghilangkan 1.421 keberhasilan nyata. Himpunan `progress=='Placement'` (7.534) bersarang penuh di dalam `rejection=='Placement'` (8.955); union keduanya = 8.955, identik dengan definisi ini.

**(b) `stage == 'Placement'` — definisi OPERASIONAL (posisi tahap saat ini):**

```python
mask = df['progress_student'] == 'Placement'   # 7.534 baris
```

Dipakai HANYA untuk menampilkan "proses yang tahapannya saat ini Placement": bar terbawah funnel Monitoring dan tampilan tahap di Beranda.

**Aturan tampilan wajib:** karena dua angka (7.534 vs 8.955) tampil di halaman berbeda, footer Monitoring dan Analitik WAJIB memuat kalimat penjelasan selisih 1.421 (placement yang diarsipkan ke Finish) supaya juri tidak mengira ada inkonsistensi. Teks contoh ada di Bagian 6.

**Sumber kebenaran placement = tracking_student SAJA.** `ketersediaan=='Placed'` di status_student TIDAK dipakai sebagai sumber placement (keputusan final tim; lihat 4.10).

### 4.2 Success rate BT-04 — `[HITUNG-ULANG]` (angka mockup 18,1%/50,5% SUDAH TIDAK BERLAKU)

Basis data: `ts_bersih = tracking_student[~is_anomali]` (41.600 − 2.578 = **39.022** baris).

**(a) Per-pengiriman (konversi per proses):**

```python
rate = (ts_bersih['rejection']=='Placement').sum() / len(ts_bersih)
# = 8.955 / 39.022 ≈ 22,9%
```

(Numerator tidak terpengaruh filter anomali karena baris anomali ber-`rejection 'On Progress'`, mustahil `'Placement'`.)

**(b) Per-mahasiswa (keberhasilan per orang):**

```python
numerator   = ts_bersih.loc[ts_bersih['rejection']=='Placement', 'NIM'].nunique()   # = 5.759
denominator = ts_bersih['NIM'].nunique()   # NIM unik pernah dikirim, setelah saring anomali
rate = numerator / denominator
```

Denominator ≤ 10.174 (mahasiswa yang SELURUH barisnya anomali ikut tersaring — jumlah pastinya dihitung builder, jangan hardcode).

**Aturan seragam:** SEMUA success rate di mana pun (headline, tren per bulan/semester, per segmen, per perusahaan/liga Wilson) memakai basis `ts_bersih` dan numerator `rejection=='Placement'`. Tidak ada pengecualian.

**Headline vs sekunder:** keduanya ditampilkan berdampingan di Analitik dengan penjelasan selisih (satu mahasiswa dikirim ke banyak perusahaan, cukup berhasil di satu). Mana yang jadi headline `[OWNER-DECIDED: Andalan]` — bangun keduanya setara dulu.

### 4.3 Eligible (BT-06)

```python
is_eligible = status_student['ketersediaan'] == 'Available'    # 7.135 mahasiswa
```

- Konfirmasi resmi panitia: kolom "eligible" = kolom `ketersediaan`.
- **1.448** dari 7.135 ber-`CV == 'Tidak Ada'`. Keputusan tim: mereka TETAP eligible (tidak dikecualikan dari gerbang mana pun), tetapi diberi **badge "tanpa CV"** di Matching dan Beranda. CV/portofolio/IPK adalah faktor kualitas, bukan gerbang.

### 4.4 Segmen "Eligible, belum dikirim" (Beranda) — `[HITUNG-ULANG]`

```python
sent_nims = set(tracking_student['NIM'])
mask = (status_student['ketersediaan']=='Available') & (~status_student['NIM'].isin(sent_nims))
```

**Catatan perubahan definisi:** angka 651 di mockup lama dihitung dengan filter tambahan `CV=='Ada'`. Definisi final TIDAK memfilter CV (konsisten dengan 4.3); jumlah barunya lebih besar dan dihitung builder. Badge "tanpa CV" tetap ditampilkan per baris.

### 4.5 Aturan FU & Ghosting (BT-05) — aturan resmi panitia, tervalidasi

Dihitung dari `send_date` (join tracking_student → tracking_company via `id_tracking_company`):

| Umur sejak send_date | Status seharusnya |
|---|---|
| > 7 hari | FU 1 |
| > 14 hari | FU 2 |
| > 21 hari | FU 3 |
| > 28 hari | Ghosting |

Tervalidasi: seluruh 2.905 baris `progress 'Ghosting'` berumur >28 hari dan eskalasi FU terurut. **Pakai label `progress_student` yang sudah ada di data sebagai sumber status FU/Ghosting** (jangan hitung ulang live terhadap ANCHOR — pada snapshot beku SEMUA proses aktif sudah >28 hari, sehingga hitung-ulang membuat semuanya "Ghosting" dan segmen kolaps). Aturan panitia didokumentasikan sebagai *logika yang menghasilkan label tersebut*.

**Dua angka ghosting (paralel dengan 4.1):**
- Operasional (antrean Beranda): `progress_student == 'Ghosting'` → **2.905** (kasus menggantung, belum ditutup).
- Total pelaporan (agregat Monitoring): `rejection == 'Ghosting'` → **3.421** (termasuk 516 yang sudah diarsipkan ke Finish).

### 4.6 Tiga tipe ghosting (pengembangan tim — diizinkan eksplisit oleh panitia)

Asumsi dasar panitia: ghosting = perusahaan tidak merespons. Panitia mengizinkan peserta mengembangkan sudut pandang lain dari eksplorasi data. Pengembangan tim: bandingkan urutan `last_update`.

Untuk **setiap baris ghosting** (pakai himpunan yang relevan per konteks, 2.905 atau 3.421):

```python
# placements milik mahasiswa yang sama, referensi = definisi placement resmi (4.1a)
pl = ts[(ts['NIM']==nim) & (ts['rejection']=='Placement')]['last_update']
if pl.empty:                       tipe = 'murni_perusahaan'   # tak pernah placed di mana pun
elif pl.min() <  t_ghosting:       tipe = 'mahasiswa_mangkir'  # ghosting SETELAH placement → kemungkinan mahasiswa berhenti merespons
elif pl.min() >  t_ghosting:       tipe = 'murni_perusahaan'   # ghosting SEBELUM placement
else:                              tipe = 'tak_tentu'          # tanggal sama persis (sangat jarang)
```

- Eksplorasi awal (referensi placement via `progress`): dari 2.406 pasangan placement×ghosting, 1.235 ghosting-setelah, 1.167 ghosting-sebelum, 4 seri. Dengan referensi `rejection` angkanya sedikit bergeser — builder hitung ulang, jangan hardcode.
- **Framing WAJIB di UI dan laporan:** ini *inferensi*, bukan label resmi. Gunakan kata "kemungkinan" ("kemungkinan mahasiswa mangkir"). `last_update` mencatat kapan status diubah, bukan pasti kapan ghosting dimulai.
- **Pemakaian:** liga "perusahaan paling sering ghosting" WAJIB menampilkan dua versi: semua ghosting (asumsi dasar) DAN ghosting `murni_perusahaan` saja — supaya perusahaan yang sebenarnya "korban mahasiswa mangkir" tidak difitnah.

### 4.7 Urgensi antrean Beranda

Urutan segmen (paling mendesak dulu): `Ghosting` (progress) → `FU 3` → `FU 1`+`FU 2` → `Interview User`+`Final Interview` → Eligible-belum-dikirim (4.4). **Di dalam segmen**, urutkan `ANCHOR − last_update` menurun (paling lama diam di atas). Alasan urutan dua-tingkat: pada snapshot beku, umur mentah tidak diskriminatif (semua tua); tahap eskalasi + staleness relatif yang membedakan. Tanpa model prediktif — setiap baris harus bisa dijelaskan dengan aturan.

Angka verifikasi segmen (basis progress_student): Ghosting 2.905, FU 3 = 1.236, FU 1 = 2.062, FU 2 = 1.657 (gabungan FU1+2 = 3.719), Interview User 3.278 + Final Interview 1.707 = 4.985.

### 4.8 KPI BT-03 (Matching)

- **Request belum dilayani:** `tracking_company.progress == 'Draft'` → **598**. (Pola data biner: sebuah request entah Draft-belum-disentuh, entah terkirim penuh; tidak ada "terkirim sebagian".)
- **Umur request:** `ANCHOR − request_date` → tampilkan "X hari sejak pengajuan" pada tiap kartu request.
- **Orphan request** (`id_talent_req` tanpa baris tracking) = **0** — laporkan sebagai temuan hygiene positif, bukan KPI hidup.
- Rasio pemenuhan agregat: 41.600 dikirim / 28.717 diminta ≈ 145% (buffer). Konteks, bukan KPI utama.

### 4.9 Skor Matching berbobot (BT-01)

**Gerbang keras (filter SEBELUM skor — kandidat gagal gerbang tidak muncul):**
1. `ketersediaan == 'Available'`
2. `semester >= minimum_semester` request

**Komponen skor (bobot default, slider-adjustable):**

| Komponen | Bobot default | Nilai komponen (0–1) |
|---|---|---|
| Prodi | 35 | 1 jika `program_studi` ∈ daftar prodi request (split koma); jika fallback klaster aktif: 0,5 untuk satu-klaster |
| Tools | 30 | jumlah tools request yang dimiliki mahasiswa / jumlah tools request |
| IPK | 20 | normalisasi, misal `min(IPK/4.0, 1)`; jika request punya IPK minimum, di bawahnya = 0 |
| Domisili | 15 | 1 jika `domisili == kota` perusahaan; HANYA aktif jika `working_arrangement` ∈ {WFO, Hybrid} |

```python
aktif  = bobot yang relevan (domisili dibuang jika WFH)
skor   = 100 * Σ(bobot_i × komponen_i) / Σ(bobot_aktif)     # selalu 0–100
```

- Slider mengubah bobot → skor & urutan dihitung ulang. **Optimasi wajib:** filter gerbang dulu (ribuan → puluhan kandidat), baru skor — jangan skor 7.135 orang per geser slider.
- Tampilkan rincian per kandidat: skor + breakdown per komponen (misal "prodi ✓ · tools 2/3 · IPK 3,61 · sekota").
- **Flag per kandidat:** "proses lain" jika NIM sudah ada di tracking_student (uncheck default — jangan kirim orang yang sedang diproses di tempat lain); "tanpa CV" jika `CV != 'Ada'`.
- Aksi akhir: **"Salin daftar NIM" / "Ekspor CSV"** — BUKAN "kirim" (dashboard tidak punya mekanisme pengiriman; CDC mengirim lewat sistem mereka sendiri).
- **Tools request:** `[OWNER-DECIDED: Mutia]`. Tidak ada kolom tools di talent_request; kebutuhan tools terkubur di teks bebas `deskripsi_requirement`. Pendekatan yang direkomendasikan: (1) bangun vocabulary dari nilai unik `status_student.tools`; (2) cari per-vocabulary dengan word boundary (`\b`); (3) tangani khusus nama satu huruf ("R", "C") — pencarian naif "R" kena 11.937 false positive; (4) lakukan SEKALI di data-prep, hasilkan kolom `tools_dibutuhkan` (list), bukan parsing runtime. Alternatif bila parsing dinilai berisiko: turunkan bobot tools / jadikan info non-skor. Builder membangun kerangka fungsi `parse_tools(deskripsi, vocab)` dengan pendekatan (1)–(4); Mutia memvalidasi hasil.

### 4.10 Diskrepansi & asumsi terdokumentasi (bahan laporan, BUKAN metrik keberhasilan)

| Fungsi | Definisi | Angka | Status |
|---|---|---|---|
| `placed_diluar_cakupan()` | `ketersediaan=='Placed'` & NIM tidak punya SATU PUN baris tracking_student | **4.163** (dari 9.301 Placed) | Interpretasi: ditempatkan di luar alur CDC (sebagian bahkan semester 2–3, di bawah syarat minimum request — konsisten dengan jalur mandiri). **BUKAN masalah sinkronisasi/BT-08** (sudah diuji: sync_date kelompok ini tidak berbeda dari yang normal). Dicatat sebagai *batasan cakupan* BT-04 |
| `placed_belum_update_status()` | punya `rejection=='Placement'` tapi `ketersediaan != 'Placed'` | **621** | **ASUMSI (bukan fakta):** jeda pembaruan status. Tidak bisa diverifikasi (tak ada log perubahan). Ini "ongkos" memilih definisi rejection — kecil (±1,5% dari 5.759), dicatat |
| Anomali | 3.1 | 2.578 | Dikecualikan dari denominator, dilaporkan sebagai isu kualitas data |

Tiga skenario yang tim asumsikan (tulis di laporan): (1) `Placed`+`rejection Placement` = disalurkan CDC dan berhasil; (2) `Placed` tanpa jejak tracking = dapat pekerjaan di luar CDC; (3) bukan-`Placed` tapi `rejection Placement` = sistem terlambat input (ASUMSI).

### 4.11 Wilson confidence interval 95% (liga perusahaan, BT-04)

```python
def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k / n
    denom  = 1 + z*z/n
    center = (p + z*z/(2*n)) / denom
    half   = z * ((p*(1-p)/n + z*z/(4*n*n)) ** 0.5) / denom
    return (center - half, center, center + half)   # (lo, titik-tengah-wilson, hi)
```

- k = placement (rejection) per perusahaan, n = pengiriman per perusahaan, keduanya dari `ts_bersih`.
- **Gate ranking: n ≥ 30.** Baris n<30 diberi badge "n kecil". 543 perusahaan lolos gate (angka bisa sedikit bergeser setelah filter anomali — builder verifikasi).
- Opsi sort: rate tertinggi / volume terbanyak / "paling andal" (CI tersempit = `hi−lo` terkecil).
- Tampilkan titik + pita CI, dengan teks penjelasan overlap (contoh gaya di mockup `Mockup/`).

### 4.12 BT-08 — dua komponen (tampil di Analitik)

**(a) Status drift — "AMAN":** bandingkan kolom salinan antara `student_all` dan `status_student` per NIM (`semester`, `program_studi`, `nama`, `email`). Hasil terverifikasi: **0 perbedaan** di seluruh 25.000 pasangan. Tampilkan badge status "AMAN — student_all dan status_student 100% konsisten". Builder tetap menghitungnya live (bukan hardcode "AMAN") supaya tetap benar bila data berganti.

**(b) Kesegaran sync:** slider X hari (default usulan 30) → tampilkan `jumlah baris dengan (SYNC_REF − sync_date) > X hari`, plus teks "data mahasiswa terakhir di-sync: {SYNC_REF}" (= 31 Jan 2025). Konteks jujur yang wajib ditulis: relatif ke ANCHOR global, seluruh data sync berumur ≥3,5 bulan karena tabel sync berhenti Januari — sebutkan di caption.

**Larangan framing:** diskrepansi 4.163 (4.10) TIDAK boleh muncul di bagian BT-08 — itu isu cakupan tracking, bukan sinkronisasi.

### 4.13 Funnel Monitoring (BT-02)

- **Urutan tahap (ASUMSI TIM, didokumentasikan):** Selecting Student by Company → CDC Briefing Student → Study Case → Interview User → Final Interview → Placement.
- **Jumlah aktif per tahap** = count `progress_student` (verifikasi: 1.673 / 1.619 / 1.678 / 3.278 / 1.707 / 7.534).
- **Gugur per gerbang** = count `rejection`: `'Rejection Screening CV'` (3.368) dipetakan ke gerbang Selecting; `'Rejection Study Case'` (2.509); `'Rejection Interview User'` (3.805); `'Rejection Final Interview'` (2.054). Tahap CDC Briefing tidak punya kategori rejection sendiri — tidak ada bar gugur di sana.
- Insight yang layak di-callout: Interview User = antrean aktif terbesar SEKALIGUS titik gugur terbesar.
- Klik tahap → cross-link ke Beranda terfilter segmen tsb (via `st.session_state`, lihat 6.1/6.3).

### 4.14 Tren waktu (BT-07)

- Basis waktu proses = `send_date` (join ke tracking_company). Bulanan ATAU per semester akademik: **Ganjil = Agustus–Januari, Genap = Februari–Juli** (label "Ganjil 2024/2025" dst).
- Per periode: volume kirim (bar) + conversion rate (line, sumbu kanan sendiri) — rate memakai aturan 4.2 (basis bersih, rejection). `[HITUNG-ULANG]` — angka tren mockup berbasis progress.
- Periode terakhir parsial (data berhenti Feb 2025 untuk send) → beri arsir/tanda "periode belum lengkap".

---

## BAGIAN 5 — KONSTANTA (`config.py` dan `core/schema.py`)

### 5.1 `core/schema.py` — nilai kategori sebagai konstanta (anti-typo)

```python
# progress_student (12 nilai)
STAGE_SELECTING  = 'Selecting Student by Company'
STAGE_BRIEFING   = 'CDC Briefing Student'
STAGE_STUDYCASE  = 'Study Case'
STAGE_INTERVIEW  = 'Interview User'
STAGE_FINAL      = 'Final Interview'
STAGE_PLACEMENT  = 'Placement'
STAGE_FU1, STAGE_FU2, STAGE_FU3 = 'FU 1', 'FU 2', 'FU 3'
STAGE_GHOSTING   = 'Ghosting'
STAGE_REJECTED   = 'Rejected'
STAGE_FINISH     = 'Finish'

# rejection (7 nilai)
REJ_ONPROGRESS   = 'On Progress'
REJ_PLACEMENT    = 'Placement'
REJ_GHOSTING     = 'Ghosting'
REJ_CV           = 'Rejection Screening CV'
REJ_STUDYCASE    = 'Rejection Study Case'
REJ_INTERVIEW    = 'Rejection Interview User'
REJ_FINAL        = 'Rejection Final Interview'

# ketersediaan
AVAIL_AVAILABLE, AVAIL_PLACED, AVAIL_INACTIVE = 'Available', 'Placed', 'Tidak Aktif'

FUNNEL_ORDER = [STAGE_SELECTING, STAGE_BRIEFING, STAGE_STUDYCASE,
                STAGE_INTERVIEW, STAGE_FINAL, STAGE_PLACEMENT]
REJ_GATE_MAP = {STAGE_SELECTING: REJ_CV, STAGE_STUDYCASE: REJ_STUDYCASE,
                STAGE_INTERVIEW: REJ_INTERVIEW, STAGE_FINAL: REJ_FINAL}
```

### 5.2 `config.py`

```python
DATA_DIR = "../Data/Raw"            # path relatif dari dashboard/; jadikan mudah diubah
FILES = { ... }                      # nama keenam CSV
FU_THRESHOLDS = {"FU1": 7, "FU2": 14, "FU3": 21, "GHOSTING": 28}   # hari, aturan panitia
WILSON_Z = 1.96
MIN_N_RANKING = 30
BOBOT_DEFAULT = {"prodi": 35, "tools": 30, "ipk": 20, "domisili": 15}
SYNC_SLIDER_DEFAULT = 30            # hari
SEMESTER_GANJIL_BULAN = [8,9,10,11,12,1]   # Genap = sisanya
# PALET (dari mockup, identitas "triage desk"):
WARNA = {
  "accent":"#0f5f66", "crit":"#b42318","crit_bg":"#fdeceb",
  "warn":"#b25b06","warn_bg":"#fbf1e6", "watch":"#8a6d14","watch_bg":"#f8f3e2",
  "hot":"#155fa0","hot_bg":"#eaf1f8", "ok":"#256a3d","ok_bg":"#e9f3ec",
  "ink":"#14181a","ink2":"#4a5157","muted":"#828b90",
  "line":"#d5dad6","panel":"#ffffff","page":"#eef0ee",
  "bar":"#3a8088","barlite":"#bcd6d3","ref":"#c98a3c",
}
```

`ANCHOR` dan `SYNC_REF` TIDAK di-hardcode di config — dihitung `loader` (2.3) dan diekspos sebagai atribut hasil load.

### 5.3 18 prodi (closed set) & 6 klaster fallback Matching

| Klaster | Prodi |
|---|---|
| IT & Data | Informatika, Sistem Informasi, Pendidikan Teknik Informatika, Statistika |
| Bisnis & Ekonomi | Manajemen, Akuntansi, Ekonomi Pembangunan |
| Teknik | Teknik Industri, Teknik Elektro, Teknik Mesin, Teknik Sipil |
| Komunikasi & Kreatif | Ilmu Komunikasi, Desain Komunikasi Visual, Sastra Inggris |
| Sosial & Humaniora | Psikologi, Ilmu Hukum |
| Sains & Life | Farmasi, Agroteknologi |

Klaster hanya dipakai sebagai **fallback** saat kandidat exact-prodi < headcount (tampilkan peringatan "kandidat exact habis, menampilkan rumpun terdekat").

---

## BAGIAN 6 — RANCANGAN PER HALAMAN

**Navigasi: sidebar kiri** (struktur multipage Streamlit, folder `pages/`). Sidebar juga memuat **filter global** yang dibagikan via `st.session_state`: `jenis_penempatan`, prodi (atau klaster), rentang periode. Basis periode: `send_date` untuk tampilan proses/tracking; `request_date` untuk daftar request di Matching. Sidebar footer: indikator snapshot "Data per {ANCHOR}".

**Aturan jalur render (berlaku semua halaman):**

| Jenis elemen | Jalur | Contoh |
|---|---|---|
| Kartu KPI, badge, header, callout, tabel baca-saja | HTML custom via `st.markdown(..., unsafe_allow_html=True)`; CSS di-inject sekali dari `components/styles.py` | kartu segmen Beranda, liga Wilson |
| Chart | Plotly (atau Altair) — JANGAN chart HTML/CSS tangan | funnel, tren, bar segmen |
| Input (slider, selectbox, search, toggle, tombol filter) | Native Streamlit — wajib (jembatan event) | slider bobot, filter global |
| Tabel yang diklik → drill-down | `st.dataframe(on_select="rerun", selection_mode="single-row")` | antrean Beranda, daftar request Matching |

Fase pengerjaan: **barebones dulu** (struktur + jalur render final + data final; elemen HTML ditulis sebagai HTML polos tanpa gaya), styling (CSS/warna/font) menyusul. DILARANG membuat barebones dengan komponen native untuk elemen yang kelak jadi HTML (kerja dua kali).

Referensi visual: folder `Mockup/` di repo (`dashboard_mockup.html`, `ide_andalan*.html`) — gaya akhir mengacu ke sana, bukan spesifikasi piksel.

### 6.1 Beranda — Antrean Tindakan (BT-02 & BT-05 level individu; dikerjakan TERAKHIR, dirakit dari komponen halaman lain)

**Pertanyaan yang dijawab:** "Sebagai staf CDC, apa yang harus saya tindak SEKARANG, dan tunjukkan detailnya."

Komponen, atas ke bawah:
1. **KPI analitik ringkas** — 3–4 kartu kondisi CDC keseluruhan. `[OWNER-DECIDED: pengerja Beranda]`. Kandidat usulan: total placement 8.955 (atau 5.759 orang), success rate per-pengiriman ±22,9%, ghosting aktif 2.905, request Draft 598. Bangun kerangka 4 slot kartu.
2. **Kartu segmen urgensi** (5 kartu, klik = filter antrean; lihat 4.7): Ghosting → FU3 → FU1&2 → Interview → Eligible-belum-dikirim. Judul + jumlah + isi tabel berubah BERSAMA saat kartu diklik. Segmen Eligible memakai bentuk kolom berbeda (tanpa "tahap/diam"; ganti prodi/IPK/domisili + badge CV).
3. **Tabel antrean** (`st.dataframe` + on_select): kolom Mahasiswa (nama+NIM), Perusahaan & posisi, Tahap (badge), Diam (hari, `ANCHOR − last_update`), Kontak (link `wa.me`). Sort default per 4.7. Search NIM/nama/perusahaan.
4. **Panel drill-down** (kolom kanan, muncul saat baris dipilih) — PEMBEDA UTAMA TIM: profil status_student (prodi, IPK, domisili, CV/portofolio, tools) + **SEMUA proses mahasiswa itu di seluruh perusahaan** (filter tracking_student by NIM) + callout otomatis bila mahasiswa sudah `rejection=='Placement'` di tempat lain: "Sudah placed di {perusahaan}. Konfirmasi dulu sebelum follow up." (1.325 mahasiswa placed-sekaligus-ghosting — kasus nyata yang ditangkap panel ini.)
5. Tombol: "Hubungi via WhatsApp" (link `wa.me` — aksi nyata) dan "Tandai ditindak" (**session-only**, simpan set NIM di `st.session_state`, beri keterangan kecil "tidak tersimpan permanen").
6. Menerima cross-link dari Monitoring: baca `st.session_state['beranda_segment']` bila di-set.

### 6.2 Matching (BT-01, BT-03, BT-06) — Mutia

**Pertanyaan:** "Untuk request ini, siapa yang paling layak dikirim, dan kenapa."

Layout dua panel:
1. **Kiri — antrean request (BT-03):** daftar kartu request terbuka. Tiap kartu tampil-diam: posisi, perusahaan, jenis penempatan, terisi X/Y (amber bila kurang), **"X hari sejak pengajuan"** (`ANCHOR − request_date`), min semester. Sort: terlama / headcount / kurang terisi. KPI atas: **598 request belum dilayani (Draft)** sebagai kartu klik-filter.
2. **Kanan — shortlist kandidat** untuk request terpilih: header request (syarat: min semester [gerbang], IPK min, daftar prodi, tools); **panel bobot slider** (4.9, default 35/30/20/15, tombol reset, catatan "gerbang wajib bukan bobot"); tabel kandidat urut skor dengan breakdown komponen + flag "proses lain" / "tanpa CV" + checkbox; tombol **"Salin daftar NIM" / "Ekspor CSV"**.
3. Fallback klaster prodi (5.3) dengan peringatan bila kandidat exact < headcount.
4. Parsing tools `[OWNER-DECIDED: Mutia]` per 4.9.

### 6.3 Monitoring (BT-02 & BT-05 level pipeline; sebagian BT-04) — Afrizal

**Pertanyaan:** "Di mana pipeline bocor, dan pola apa yang sistemik."

1. **Toggle `mahasiswa | perusahaan`** di atas (pakai `st.tabs` atau segmented control — tab DALAM halaman diperbolehkan; yang dilarang hanya tab sebagai navigasi utama).
2. **Sisi mahasiswa:** funnel per 4.13 (aktif per tahap + gugur per gerbang, Plotly horizontal), callout kebocoran terbesar, klik tahap → set `st.session_state['beranda_segment']` + `st.switch_page` ke Beranda. Tabel ringkas performa perusahaan (top/bottom acceptance, Wilson + badge n kecil) versi ringkas — versi penuh di Analitik.
3. **Sisi perusahaan:** `[OWNER-DECIDED: Afrizal]`. Kerangka usulan yang builder siapkan: status request per perusahaan, waktu-respons, dan **detail ghosting** — total 3.421 (rejection) vs aktif 2.905 (progress), breakdown **tiga tipe** (4.6), liga "paling sering ghosting" DUA versi (semua vs murni-perusahaan), temuan "tersebar bukan segelintir pelaku" (maks per perusahaan ±14 kasus).
4. Footer definisi (WAJIB): jelaskan 7.534 vs 8.955 (Bagian 4.1) dan bahwa funnel memakai progress_student sedangkan gugur memakai rejection; `tracking_company.progress` tidak dipakai.

### 6.4 Analitik (BT-04 penuh, BT-07, BT-08) — Andalan

**Pertanyaan:** "Bagaimana kinerja program secara keseluruhan — laporan untuk pimpinan."

1. **Dual success rate** (4.2) `[HITUNG-ULANG]`: dua kartu besar (per-pengiriman ±22,9%; per-mahasiswa 5.759/denominator) + panel "kenapa berbeda". Headline final `[OWNER-DECIDED: Andalan]`.
2. **Tren waktu** (4.14): toggle Bulanan|Per semester, bar volume + line rate (sumbu kanan), arsir periode parsial.
3. **Segmentasi:** rate per prodi & per sektor, bar mulai dari NOL (dilarang truncate axis), garis referensi rata-rata keseluruhan, n per baris, outlier kecil-sampel di-badge. Temuan jujur yang ditulis: kinerja konsisten lintas segmen (jangan mendramatisasi selisih kecil).
4. **Liga perusahaan penuh** (4.11): Wilson CI, gate n≥30, tiga opsi sort termasuk "paling andal".
5. **BT-08** (4.12): badge drift "AMAN" (dihitung live) + slider kesegaran sync relatif `SYNC_REF` + teks "terakhir di-sync 31 Jan 2025".
6. **Catatan cakupan & kualitas data** (4.10): 4.163 Placed-di-luar-CDC (batasan cakupan), 2.578 anomali dikecualikan, 621 asumsi jeda input. Satu blok teks, bukan chart.
7. Tombol **Cetak** & **Ekspor laporan (PDF)** — minimal print-friendly CSS; PDF penuh nice-to-have.

---

## BAGIAN 7 — STRUKTUR FOLDER & URUTAN PEMBANGUNAN

Buat folder baru `dashboard/` di root repo (sejajar `Data/`, `Mockup/`, `Notebooks/`):

```
dashboard/
├── app.py                  # entry point; st.set_page_config; sidebar bersama; halaman default → Beranda
├── config.py               # Bagian 5.2
├── requirements.txt        # streamlit, pandas, numpy, plotly
├── core/
│   ├── __init__.py
│   ├── schema.py           # Bagian 5.1
│   ├── loader.py           # Bagian 2 (delimiter, dtype, tanggal, ANCHOR, SYNC_REF); bungkus @st.cache_data
│   ├── clean.py            # Bagian 3 (flag anomali, list_nim_bersih, telepon, parsing multi-value)
│   └── metrics.py          # Bagian 4 — SEMUA definisi; tidak ada rumus metrik di luar file ini
├── components/
│   ├── __init__.py
│   ├── styles.py           # blok CSS global (inject sekali); palet dari config.WARNA
│   ├── html.py             # generator HTML: kartu KPI, badge tahap, kartu segmen, tabel-baca, callout
│   └── tables.py           # tabel interaktif (st.dataframe+on_select) + panel drill-down
└── pages/
    ├── 1_Beranda.py
    ├── 2_Matching.py
    ├── 3_Monitoring.py
    └── 4_Analitik.py
```

**Urutan bangun (WAJIB berurutan untuk fondasi):**
1. `config.py` + `core/schema.py` + `core/loader.py` + `core/clean.py` + `core/metrics.py` — fondasi bersama, dikunci lebih dulu. Jalankan checklist Bagian 10 sampai lolos semua.
2. `components/` kerangka (styles kosong dulu boleh; html/tables berfungsi polos).
3. `pages/` — **paralel**: Matching (Mutia), Monitoring (Afrizal), Analitik (Andalan).
4. `1_Beranda.py` — terakhir, oleh siapa pun yang selesai lebih dulu; merakit: logika ghosting (dari kerjaan Monitoring), drill-down per-NIM (dari kerjaan Matching), layout & KPI (dari kerjaan Analitik/shell).
5. Styling menyeluruh (CSS di `styles.py`) setelah semua barebones jalan.

Aturan kolaborasi: `core/` dan `config.py` hanya diubah lewat kesepakatan tim (perubahan definisi = perubahan dokumen ini dulu). `pages/` bebas per pemilik. `components/` koordinasi ringan.

---

## BAGIAN 8 — ASUMSI & KEPUTUSAN TERDOKUMENTASI (untuk laporan panitia)

Panitia mewajibkan peserta menjelaskan asumsi dan metode cleansing secara eksplisit. Daftar final:

1. **Placement = `rejection == 'Placement'`** (bukan `progress_student`), karena 1.421 baris Finish+Placement adalah keberhasilan sah yang diarsipkan; kombinasi itu konsisten, bukan anomali. (Panitia menyerahkan definisi ke peserta.)
2. **Baris Finish+On Progress (2.578) = anomali** (dikonfirmasi panitia sebagai noise) → di-flag, dikecualikan dari seluruh perhitungan keberhasilan, dilaporkan jumlahnya.
3. **Sumber kebenaran placement = tracking_student saja.** `ketersediaan=='Placed'` diabaikan sebagai sumber placement; 4.163 mahasiswa Placed-tanpa-jejak dicatat sebagai *ditempatkan di luar alur CDC* (batasan cakupan BT-04, bukan BT-08).
4. **621 mahasiswa** ber-placement dengan `ketersediaan` belum Placed → **diasumsikan** jeda pembaruan status (tidak dapat diverifikasi; ditulis sebagai asumsi).
5. **Ghosting**: asumsi dasar panitia = pihak perusahaan; tim mengembangkan pembedaan tiga tipe via urutan `last_update` (diizinkan eksplisit oleh panitia), disajikan sebagai inferensi ("kemungkinan"), dan liga perusahaan menampilkan dua versi.
6. **Urutan funnel** Selecting → CDC Briefing → Study Case → Interview User → Final Interview → Placement = asumsi tim (tidak ditetapkan panitia).
7. **Anchor waktu = tanggal termutakhir dataset (17 Mei 2025)**, bukan tanggal hari ini, karena data snapshot beku. Kesegaran sync relatif ke sync terakhir (31 Jan 2025).
8. `request_date` < `created_at` = perilaku normal sistem; `created_at` tidak dipakai.
9. Eligible = `ketersediaan=='Available'` (konfirmasi panitia); mahasiswa Available tanpa CV tetap eligible, ditandai.
10. `tracking_company.progress` tidak dipakai untuk funnel (tidak sinkron dengan detail); tracking_student = sumber kebenaran pengiriman; 48 `list_nim` rusak direkonstruksi via kode.
11. Keberhasilan dihitung per-pengiriman DAN per-mahasiswa (dua sudut yang sama-sama valid; keduanya ditampilkan dengan penjelasan).

## BAGIAN 9 — ARSIP TANYA-JAWAB PANITIA (dasar keputusan)

| Pertanyaan tim | Jawaban panitia (inti) | Konsekuensi |
|---|---|---|
| Eligible = ketersediaan? Kolom tracking_company 13 vs 14? | Ya, eligible = `ketersediaan`. Dokumentasi salah tulis; 13 kolom benar | 4.3; Bagian 1 |
| Beda progress_student vs rejection; "On Progress" di kolom "status akhir"; kombinasi Finish+On Progress? | progress = tahapan berjalan; rejection = status proses; "On Progress" disengaja = belum final; Finish+On Progress = **noise/anomali**, penanganan diserahkan peserta; definisi Placement dibebaskan asal logis & didokumentasikan | 3.1; 4.1; 4.2 |
| Ghosting dari perusahaan saja? Boleh dibedakan via last_update? | Asumsi dasar: perusahaan. Peserta **dibebaskan** mengembangkan sudut pandang/pembedaan sumber dari eksplorasi data | 4.6 |
| Aturan FU/Ghosting | >1mg FU1, >2mg FU2, >3mg FU3, >4mg Ghosting, dari send_date | 4.5 |
| Perbaikan list_nim | Diumumkan, tapi file tetap identik → tim rekonstruksi sendiri | 3.4 |

---

## BAGIAN 10 — CHECKLIST VERIFIKASI (jalankan setelah fondasi selesai; SEMUA harus persis)

| # | Pemeriksaan | Nilai wajib |
|---|---|---|
| 1 | Bentuk enam tabel (baris×kolom) | 1500×9; 12000×19; 25000×10; 25000×15; 12000×13; 41600×11 |
| 2 | `ANCHOR` | 2025-05-17 |
| 3 | `SYNC_REF` | 2025-01-31 |
| 4 | `is_anomali.sum()` | 2.578 |
| 5 | Baris `rejection=='Placement'` | 8.955 |
| 6 | Baris `progress_student=='Placement'` | 7.534 |
| 7 | Baris Finish+Placement | 1.421 |
| 8 | NIM unik `rejection=='Placement'` | 5.759 |
| 9 | Success rate per-pengiriman | 8.955 / 39.022 ≈ 22,9% |
| 10 | `progress=='Ghosting'` / `rejection=='Ghosting'` | 2.905 / 3.421 |
| 11 | FU1 / FU2 / FU3 (progress) | 2.062 / 1.657 / 1.236 |
| 12 | Interview User / Final Interview (progress) | 3.278 / 1.707 |
| 13 | Eligible (`Available`) / di antaranya tanpa CV | 7.135 / 1.448 |
| 14 | Request `progress=='Draft'` | 598 |
| 15 | `ketersediaan=='Placed'` / tanpa jejak tracking | 9.301 / 4.163 |
| 16 | Placement (rejection) dengan `ketersediaan != 'Placed'` (NIM) | 621 |
| 17 | Orphan `id_talent_req` (dua arah) | 0 / 0 |
| 18 | `list_nim` rusak terekonstruksi | 48 / 48 |
| 19 | Drift student_all vs status_student (semester & prodi) | 0 / 0 |
| 20 | NIM unik pernah dikirim (sebelum filter anomali) | 10.174 |
| 21 | Umur negatif dengan ANCHOR benar | 0 |

Angka yang TIDAK boleh di-hardcode dan dihitung builder: denominator per-mahasiswa setelah filter anomali; jumlah eligible-belum-dikirim (definisi baru 4.4); pembagian tiga tipe ghosting dengan referensi rejection; jumlah perusahaan lolos gate n≥30 pada basis bersih; seluruh angka tren per periode.

---

*Dokumen ini menggantikan semua angka dan definisi pada mockup HTML sebelumnya bila bertentangan. Perubahan definisi apa pun harus diperbarui DI DOKUMEN INI lebih dulu, baru di kode.*