# TalentTrack SSDC — Panduan Fase 0

Dashboard Streamlit untuk Student Placement System (SSDC).
6 tabel, 79 kolom, ~18MB total.

**Yang dilakukan sekarang dulu: Data Profiling.**
Semua keputusan desain dashboard ditunda sampai meeting Rabu. Baca dulu bentar.

---

## 0. Goal
**Meeting dengan gambaran tentang seberapa bisa dipercaya data ini**

---

## 1. Pembagian

Tiap orang ambil cluster tabel yang berhubungan antartabelnya.

| Orang | Cluster | File |
|---|---|---|
| Andalan | Sisi perusahaan | `company.csv`, `talent_request.csv` |
| Mutia | Sisi mahasiswa | `student_all.csv`, `status_student.csv` |
| Afrizal | Sisi tracking | `tracking_company.csv`, `tracking_student.csv` |

---

## 2. Checklist universal (dijalankan semua orang, di kedua file cluster-nya)

Sebelum masuk ke pemeriksaan spesifik, jalankan ini di **setiap** file:

### 2.1 Bentuk & struktur
- Jumlah baris dan kolom. Cocok dengan dokumentasi? (company=9, talent_request=19, student_all=10, status_student=16, tracking_company=14, tracking_student=11)
- Apakah ada kolom **tak terduga** yang tidak ada di dokumentasi? (khususnya `tracking_company` — dokumentasi menyebut kolom A dan B dipakai internal spreadsheet)
- Apakah ada kolom yang **hilang** dari yang seharusnya ada?
- Apakah nama kolom persis sama dengan ERD, atau ada beda kapitalisasi/spasi? (`NIM` vs `nim`)
- Apakah baris pertama benar-benar header, atau ada baris judul/kosong di atasnya?

### 2.2 Tipe data
- `dtype` tiap kolom hasil baca default pandas.
- Kolom yang **seharusnya numerik tapi terbaca object** — kenapa? (ada teks nyasar? koma desimal? "-"? "N/A"?)
- Kolom tanggal: apakah bisa di-`parse`? Formatnya konsisten? Ada tanggal mustahil (tahun 1900, tahun 2099)?

### 2.3 Missing values
- Persentase null per kolom.
- **Bedakan null asli vs null tersamar**: `""`, `" "`, `"-"`, `"N/A"`, `"NA"`, `"null"`, `"None"`, `"0"`, `"Belum ada"`, `"TBD"`. Cari string-string ini eksplisit.
- Apakah null-nya *bermakna*? (`send_date` kosong = belum dikirim, itu informasi, bukan error)

### 2.4 Duplikat
- Duplikat baris penuh.
- Duplikat pada **primary key**. Kalau PK duplikat, dashboard ini punya masalah serius — catat besar-besar.
- Duplikat semantik: dua perusahaan dengan nama sama tapi ID beda; dua mahasiswa dengan NIM sama tapi nama beda.

### 2.5 Kolom kategorikal — INI YANG PALING PENTING
- `value_counts(dropna=False)` untuk **setiap** kolom kategorikal. Tanpa kecuali. Tempelkan hasil lengkapnya di dokumen findings.
- Untuk tiap kolom: apakah himpunan nilainya **tertutup dan bersih**, atau ada varian penulisan?
  - Beda kapitalisasi: `Magang` / `magang` / `MAGANG`
  - Spasi berlebih: `"Magang "` / `" Magang"`
  - Sinonim: `Magang` / `Internship` / `PKL` / `Intern`
  - Typo: `Fulltime` / `Full-time` / `Full Time` / `Ful-time`
  - Nilai di luar dokumentasi sama sekali
- Nilai dengan frekuensi 1–2 (long tail) — biasanya di situ typo-nya bersembunyi.

### 2.6 Format ID
- Apakah ID mengikuti format yang didokumentasikan? (`C001`, `TR001`, `SS001`, `TC001`, `TS001`)
- Ada leading zero yang hilang karena dibaca sebagai integer? (`C001` jadi `1`)
- Ada ID dengan panjang tak konsisten? (`C1` vs `C001` vs `C0001`)
- Ada whitespace di ujung ID? Ini penyebab join gagal paling sering dan paling tak terlihat.

---

## 3. Checklist spesifik per cluster

### 3.1 Cluster A — Sisi perusahaan (`company`, `talent_request`)

**Integritas relasi**
- Berapa `talent_request.id_company` yang **tidak ada** di `company.id_company`? (orphan FK)
- Berapa perusahaan di `company` yang **tidak pernah** mengajukan talent request? (wajar, tapi perlu tahu jumlahnya)
- Apakah kardinalitas benar-benar one-to-many? Ada perusahaan dengan puluhan request? Ada yang cuma 1?

**Konsistensi denormalisasi**
`talent_request` menyalin data dari `company`. Cek apakah salinannya berbohong:
- `talent_request.nama_perusahaan` vs `company.company_name` untuk `id_company` yang sama — berapa yang beda?
- `talent_request.industri_sektor` vs `company.industry_sector` — berapa yang beda?
- `talent_request.nama_pic` vs `company.pic_name` — dokumentasi bilang **boleh** beda (PIC per posisi bisa lain). Konfirmasi apakah bedanya masuk akal atau justru data kotor.
- `talent_request.no_whatsapp` vs `company.pic_phone` — sama, konfirmasi.

**Validitas nilai**
- `headcount`: integer? Ada 0? Ada negatif? Ada yang absurd (>100)? Distribusinya seperti apa?
- `minimum_semester`: rentangnya masuk akal (1–14)? Ada 0? Ada 20?
- `request_date`: rentang tanggalnya kapan sampai kapan? Ada tanggal masa depan? Ada tanggal sebelum `company.created_at` perusahaan yang bersangkutan? (request sebelum perusahaan terdaftar = anomali)
- `durasi`: ini VARCHAR bebas. Berapa banyak format berbeda? (`3 Bulan`, `3 bulan`, `3 months`, `3`, `Tidak Terbatas`) — apakah bisa di-parse jadi angka?
- `renumerasi`: VARCHAR bebas juga. Bisa di-parse jadi nominal? Berapa yang Non-Paid? Berapa format berbeda? (`Rp 1.500.000/bulan`, `1500000`, `1,5jt`, `Unpaid`)
- `bidang_studi_dibutuhkan`: dokumentasi bilang **bisa lebih dari satu prodi**. Bagaimana pemisahnya? Koma? Slash? "dan"? Ini penting untuk matching nanti.
- `alamat_kantor` & `deskripsi_requirement`: TEXT panjang. Ada yang kosong? Ada yang isinya cuma "-"?

**Value counts wajib**
`company_type`, `industry_sector`, `kota`, `skala_perusahaan`, `jenis_penempatan`, `working_arrangement`, `industri_sektor`, `sumber_baris_form`

---

### 3.2 Cluster B — Sisi mahasiswa (`student_all`, `status_student`)

**Integritas relasi**
Dokumentasi mengklaim relasi **one-to-one** via NIM. Buktikan:
- Berapa `status_student.nim` yang tidak ada di `student_all.nim`? (orphan)
- Berapa `student_all.nim` yang tidak punya record di `status_student`? (mahasiswa tanpa status = tidak bisa dikirim)
- Apakah `status_student.nim` benar-benar UNIQUE? Ada NIM dengan lebih dari satu record status?
- Kalau one-to-one tidak terpenuhi, **berapa besar pelanggarannya**? 5 baris atau 500?

**Konsistensi denormalisasi**
`status_student` menyalin `nama`, `semester`, `program_studi` dari `student_all`. Cek:
- `nama` beda untuk NIM yang sama — berapa? (kalau ada, salah satu tabel salah, dan kita harus tahu mana yang dipercaya)
- `semester` beda untuk NIM yang sama — berapa? Ini kemungkinan besar **memang beda** karena `sync_date`. Cek: apakah `status_student.semester` selalu ≥ `student_all.semester`, atau ada yang mundur?
- `program_studi` beda untuk NIM yang sama — berapa? Ini seharusnya tidak pernah beda. Kalau beda, ada masalah.

**Validitas nilai**
- `nim`: formatnya konsisten? Panjangnya sama semua? Terbaca sebagai string atau integer (leading zero hilang)?
- `ipk`: numerik? Rentangnya 0.00–4.00? Ada yang >4 (skala beda)? Ada yang 0 (belum ada nilai vs benar-benar 0)? Ada null? Distribusinya masuk akal atau ada spike aneh?
- `semester`: rentang 1–14 masuk akal? Ada 0? Ada 20+?
- `sync_date`: rentangnya kapan? Berapa banyak record yang **sync-nya sudah lama** (data usang)? Ada null?
- `email_pribadi` / `email_kampus` / `email`: format valid (ada `@`)? Ada duplikat email lintas NIM? (indikasi data kotor)
- `hp` / `no_whatsapp`: formatnya seragam? (`08xx`, `+628xx`, `628xx`, ada spasi/strip?) Ada yang jelas bukan nomor?
- `bulan_masuk`: format `"Agustus 2021"`? Bisa di-parse? Konsisten? Apakah cocok dengan `semester` (mahasiswa masuk 2021, sekarang semester 6 — masuk akal)?

**Kolom `tools` — perhatian khusus**
- Pemisahnya apa? Koma? Semicolon? Campur?
- Ada berapa tools unik setelah di-split dan di-strip?
- Seberapa kotor? (`Python` / `python` / `Phyton` / `Python3` / `Py`)
- Berapa mahasiswa yang `tools`-nya kosong?
- Berapa tools rata-rata per mahasiswa? Ada yang punya 50 tools (mengisi asal)?

**Kolom kelayakan — ini penentu funnel**
- `status` (Active/Inactive/Cuti/Lulus): sebaran? Nilai di luar dokumentasi?
- `ketersediaan` (Available/Placed/Tidak Aktif): sebaran? Nilai di luar dokumentasi?
- `cv` & `portofolio` (Ada/Tidak Ada): sebaran? Ada nilai ketiga?
- **Apakah `status` dan `ketersediaan` pernah bertentangan?** Contoh: `status = Lulus` tapi `ketersediaan = Available`. Buat crosstab dua kolom ini — ini salah satu tabel paling informatif yang akan kamu bawa ke meeting.
- Catatan: dokumentasi menyebut kolom `eligible` sebagai penentu utama, tapi **kolom itu tidak ada di ERD maupun daftar kolom**. Konfirmasi: apakah benar-benar tidak ada, atau ada dengan nama lain? Ini pertanyaan meeting.

**Value counts wajib**
`program_studi`, `bidang_minat`, `jenis_penempatan_diminati`, `status`, `ketersediaan`, `cv`, `portofolio`, `domisili`, `bulan_masuk`

---

### 3.3 Cluster C — Sisi tracking (`tracking_company`, `tracking_student`)

Ini cluster paling berat. Kerjakan `list_nim` **lebih dulu**, sebelum yang lain.

**`list_nim` — jantung seluruh dashboard**
Kolom ini adalah jembatan antara sisi perusahaan dan sisi mahasiswa. Kalau rusak, desain dashboard berubah.
- Pemisahnya apa? Koma? Ada spasi setelah koma? Konsisten?
- Explode jadi baris per NIM. Total NIM hasil explode: berapa?
- Apakah format NIM di `list_nim` sama dengan `student_all.nim`? (string vs int, leading zero, whitespace)
- Berapa NIM di `list_nim` yang **tidak ada** di `student_all`? (NIM hantu)
- Ada NIM duplikat di dalam satu `list_nim` yang sama?
- Ada `list_nim` yang kosong? Berapa? Apakah itu berarti belum dikirim?
- **Apakah `jumlah_dikirimkan` sama dengan jumlah elemen di `list_nim`?** Berapa baris yang tidak cocok? Ini cek konsistensi paling penting di seluruh dataset.

**Rekonsiliasi `list_nim` ↔ `tracking_student` — cek paling kritis**
Ada dua cara merepresentasikan "mahasiswa X dikirim ke posisi Y". Kedua sumber ini harus setuju:
- Buat set pasangan `(id_tracking_company, nim)` dari hasil explode `list_nim`.
- Buat set pasangan `(id_tracking_company, nim)` dari `tracking_student`.
- Berapa yang ada di `list_nim` tapi **tidak ada** di `tracking_student`? (dikirim tapi tidak ditrack)
- Berapa yang ada di `tracking_student` tapi **tidak ada** di `list_nim`? (ditrack tapi tidak tercatat dikirim)
- Kalau kedua angka ini besar, **salah satu sumber tidak bisa dipercaya**, dan meeting harus memutuskan mana yang jadi acuan funnel. Bawa angka konkretnya.

**Integritas relasi**
- `tracking_company.id_talent_req` → `talent_request`: berapa orphan?
- `tracking_company.id_company` → `company`: berapa orphan?
- `tracking_student.nim` → `student_all`: berapa orphan?
- `tracking_student.id_tracking_company` → `tracking_company`: berapa orphan?
- Apakah `tracking_company.id_company` **konsisten** dengan `id_company` dari `talent_request` yang direferensikannya? (dua jalur ke perusahaan yang sama — pernah bertentangan?)
- Berapa `talent_request` yang **tidak punya** record `tracking_company` sama sekali? (request masuk tapi tidak pernah diproses = insight nyata)

**Konsistensi jumlah**
- Apakah `tracking_company.jumlah_permintaan` sama dengan `talent_request.headcount` untuk `id_talent_req` yang sama? Berapa yang beda?
- Berapa baris di mana `jumlah_dikirimkan` > `jumlah_permintaan`? (dokumentasi bilang ini **wajar** — buffer. Konfirmasi seberapa sering.)
- Berapa baris di mana `jumlah_dikirimkan` = 0 tapi `progress` bukan Draft?
- Berapa mahasiswa aktual per `id_tracking_company` di `tracking_student` — cocok dengan `jumlah_dikirimkan`?

**Kolom status — sumber kebingungan utama**
Ada tiga kolom status yang saling tumpang tindih: `tracking_company.progress`, `tracking_student.progress_student`, `tracking_student.rejection`.
- `value_counts` ketiganya. Nilai apa saja yang **tidak ada** di dokumentasi?
- Dokumentasi menyebut `Rejected` di `progress_student` tapi `Rejection Screening CV` dst di `rejection`. Cek nilai aktualnya — cocok atau tidak?
- **Crosstab `progress_student` × `rejection`.** Cari kombinasi yang tidak masuk akal:
  - `progress_student = Placement` tapi `rejection = Rejection Interview User`
  - `progress_student = Ghosting` tapi `rejection = On Progress`
  - `progress_student = Rejected` tapi `rejection = Placement`
  - Berapa baris yang kontradiktif? Bawa angkanya.
- Apakah `tracking_company.progress` konsisten dengan status anak-anaknya di `tracking_student`? (`progress = Closed` tapi anaknya masih `Interview User`?)
- Apakah nilai `progress_student` menyiratkan urutan tahapan yang jelas, atau ada nilai yang tidak bisa diurutkan? (`CDC Briefing Student` muncul sebelum atau sesudah `Study Case`?) — ini kritis untuk membangun funnel.

**Validitas tanggal**
- `request_date` ≤ `send_date`? Berapa baris yang terbalik?
- `tracking_company.request_date` sama dengan `talent_request.request_date` untuk request yang sama? Berapa yang beda?
- `tracking_student.last_update` ≥ `tracking_company.send_date`? Berapa yang terbalik?
- Berapa `send_date` yang kosong? Apakah semuanya `progress = Draft`?
- Rentang `last_update`: kapan data terakhir diperbarui? Ada record yang sangat lama tidak di-update? (bahan mentah untuk deteksi ghosting)

**Denormalisasi**
- `tracking_company.nama_perusahaan` vs `company.company_name` — berapa yang beda?
- `tracking_company.posisi` vs `talent_request.nama_posisi` — berapa yang beda?
- `tracking_company.bidang_studi_dicari` vs `talent_request.bidang_studi_dibutuhkan` — berapa yang beda?
- `tracking_student.student_name` vs `student_all.nama` — berapa yang beda?
- `tracking_student.company` vs `company.company_name` — berapa yang beda?
- `tracking_student.position` vs `talent_request.nama_posisi` — berapa yang beda?

**Value counts wajib**
`progress`, `progress_student`, `rejection`, `jenis_penempatan` (kedua tabel), `posisi`, `position`, `bidang_studi_dicari`, `internship_semester`

---

## 4. Format deliverable (sama untuk semua orang)

Satu notebook per cluster di `notebooks/`, plus **satu dokumen findings bersama** yang kalian bertiga tulis di bagian masing-masing.

Struktur bagian findings:

```markdown
## Findings — <nama cluster>
Ditulis oleh: <nama>
Tanggal: <tanggal>

### Ringkasan 3 kalimat
Apa kondisi umum data ini. Apa temuan terbesar. Apa yang paling mengkhawatirkan.

### Bentuk data
| File | Baris | Kolom | Sesuai dokumentasi? |

### Value counts semua kolom kategorikal
(tempel lengkap — jangan diringkas)

### Integritas FK
| Relasi | Total | Orphan | % |

### Kontradiksi & anomali
(daftar konkret, dengan jumlah baris)

### Nilai di luar dokumentasi
(kolom mana, nilai apa, berapa banyak)

### Pertanyaan terbuka untuk meeting
1. ...
2. ...
```

**Aturan penulisan temuan:** selalu sertakan **angka**, jangan hanya sifat.
Tulis "47 dari 1.203 baris (3,9%) punya `progress_student = Placement` tapi `rejection = Rejection`", bukan "ada beberapa yang tidak konsisten".
Angka bisa dipakai untuk memutuskan sesuatu. Kata sifat tidak bisa.

---

## 5. Do / Don't di Fase 0

### DO
- Profiling, dokumentasikan, tulis temuan **dengan angka**.
- Perbaiki hanya masalah yang **jelas dan internal cluster**: strip whitespace, normalisasi case, cast dtype.
- Catat setiap asumsi yang kamu ambil, sekecil apa pun.
- Tulis isu yang belum terjawab di "Pertanyaan terbuka", lalu **lanjut jalan**.
- Perlakukan data kotor sebagai **temuan**, bukan aib yang harus disembunyikan. Kualitas data yang buruk adalah insight yang bisa dipresentasikan.

### DON'T
- **Jangan bikin business logic.** "Mahasiswa Inactive tidak dihitung di funnel" adalah keputusan meeting.
- **Jangan bikin matching score.**
- **Jangan merge tabel di luar cluster-mu.** (Kecuali untuk cek FK — itu boleh dan wajib.)
- **Jangan tentukan tahapan funnel, definisi KPI, atau threshold ghosting sendirian.**
- **Jangan hapus baris.** Kalau ada baris aneh, catat, jangan buang. Meeting yang memutuskan.
- **Jangan berhenti nunggu jawaban.** Tulis pertanyaannya, lanjut kerja.
- **Jangan sentuh `app.py`.** Belum ada, dan memang belum boleh ada.
- **Jangan edit CSV mentah.** Semua cleaning lewat kode, supaya reproducible.

Alasannya sederhana: kalau tiga orang mengambil keputusan business logic secara independen,
kita akan menghabiskan satu hari penuh untuk membatalkan dua dari tiga versi.

---

## 6. Transisi ke Fase 1 — apa yang dibahas di meeting

Fase 0 selesai saat semua orang sudah menempelkan temuannya ke dokumen bersama.
Meeting adalah tempat semua keputusan yang ditunda selama Fase 0 dijawab sekaligus.

**Agenda meeting (urut, jangan dibalik):**

1. **Review temuan** (~30 menit)
   Tiap orang presentasi 5 menit. Fokus ke tiga hal: apa yang rusak, seberapa parah, apa implikasinya.

2. **Putuskan sumber kebenaran**
   Kolom denormalisasi mana yang dipercaya. `company.company_name` atau salinannya?
   `list_nim` atau `tracking_student`? Ini harus dijawab sebelum apa pun dibangun.

3. **Kunci definisi metrik**
   Apa itu "dikirim"? Apa itu "placed"? Tahapan funnel apa saja dan urutannya bagaimana?
   Siapa yang dihitung "eligible"? Berapa hari tanpa update sampai disebut "ghosting"?
   Setiap definisi ditulis dan disepakati **sebelum** ada yang menulis kode metrik.

4. **Tentukan aturan cleaning bersama**
   Berdasarkan value counts semua orang: mapping normalisasi kategori, penanganan null,
   baris mana yang di-drop (kalau ada) dan atas dasar apa.

5. **Tetapkan bentuk dashboard**
   Berapa halaman, isinya apa, tiap halaman fungsinya apa.

6. **Bagi ulang peran untuk Fase 1**
   Fase 1 dibagi per **layer** (data/metrics, analytics/charts, app shell/UX), bukan per halaman.
   Detailnya menyusul setelah meeting.

**Yang harus kamu bawa ke meeting:** notebook profiling-mu, bagian findings-mu yang sudah lengkap,
dan daftar pertanyaan terbukamu. Tanpa ketiganya, meeting-nya jadi tebak-tebakan.