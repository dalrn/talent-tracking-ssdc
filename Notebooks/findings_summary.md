# Ringkasan Temuan Kualitas Data

Format mengikuti README bagian 4. Siap ditempel ke dokumen findings bersama.
Detail dan bukti lengkap (termasuk baris-baris temuan kritisnya) ada di tiga notebook: checking_andalan.ipynb, checking_mahasiswa.ipynb, checking_tracking.ipynb.

Sudah memperhitungkan tiga pengumuman panitia: perbaikan list_nim, aturan resmi FU dan Ghosting, dan konfirmasi bahwa eligible adalah kolom ketersediaan.

---

## Findings: Sisi Perusahaan

Ditulis oleh: Andalan
Tanggal: 15 Juli 2026

### Ringkasan 3 kalimat

Data sisi perusahaan sangat bersih: tidak ada nilai kosong, duplikat, relasi putus, maupun varian penulisan kategori. Temuan terbesar: 3.364 dari 12.000 permintaan (28%) tanggalnya lebih tua dari tanggal perusahaan terdaftar di sistem. Yang paling perlu diwaspadai bukan isi datanya tapi cara membacanya: nomor telepon berawalan nol akan rusak kalau terbaca sebagai angka.

### Bentuk data

| File | Baris | Kolom | Sesuai dokumentasi? |
|---|---|---|---|
| company.csv | 1.500 | 9 | Ya |
| talent_request.csv | 12.000 | 19 | Ya |

### Kontradiksi dan anomali

1. 3.364 dari 12.000 baris (28%): request_date lebih tua dari created_at perusahaan yang sama, selisihnya 1 sampai 693 hari (median 203 hari) dan menyangkut 780 perusahaan. **Tindak lanjut: putuskan di meeting.** Opsi: (a) anggap created_at sebagai tanggal input sistem sehingga bukan error, cukup dicatat di laporan; (b) pakai request_date sebagai satu-satunya acuan waktu dashboard.
2. 4.862 dari 12.000 baris (40,5%): PIC di talent_request beda dari PIC utama di company. Dokumentasi menyatakan ini boleh, dan nomor telepon selalu konsisten mengikuti nama PIC-nya (hanya 1 baris menyimpang). **Tindak lanjut: tidak perlu dibersihkan, pakai apa adanya.**
3. Nomor telepon tersimpan dengan awalan nol, 12 digit. **Tindak lanjut: wajib set sebagai teks saat import. Tidak perlu diskusi.**
4. 5 perusahaan tidak pernah mengajukan permintaan. **Tindak lanjut: catat saja, wajar.**

### Pertanyaan terbuka untuk meeting

1. request_date lebih tua dari created_at: anomali atau perilaku normal sistem?
2. Acuan waktu utama dashboard pakai request_date saja?

---

## Findings: Sisi Mahasiswa

Cluster milik Mutia, diprofil awal oleh Andalan sebagai referensi.
Tanggal: 15 Juli 2026

### Ringkasan 3 kalimat

Isi datanya bersih dan relasi satu banding satu antara student_all dan status_student terpenuhi sempurna, salinan kolom konsisten 100%. Panitia sudah mengonfirmasi bahwa eligible adalah kolom ketersediaan, jadi mahasiswa eligible = Available = 7.135 orang, dan 1.448 di antaranya belum punya CV padahal CV syarat minimum pengiriman. Perhatian teknis: file ini berpemisah titik koma dan nama maupun email tidak unik sehingga semua join wajib pakai NIM.

### Bentuk data

| File | Baris | Kolom | Sesuai dokumentasi? |
|---|---|---|---|
| student_all.csv | 25.000 | 10 | Ya |
| status_student.csv | 25.000 | 15 | Dokumentasi bilang 16; panitia konfirmasi eligible = ketersediaan, jadi 15 memang lengkap |

### Kontradiksi dan anomali

1. status_student.csv berpemisah titik koma. **Tindak lanjut: atur delimiter saat import. Tidak perlu diskusi.**
2. Eligible = ketersediaan Available (konfirmasi panitia) = 7.135 mahasiswa; 1.448 di antaranya CV-nya Tidak Ada. **Tindak lanjut: pakai Available sebagai definisi eligible di semua metrik; tampilkan segmen Available tanpa CV secara terpisah karena mereka belum bisa dikirim.**
3. Hanya 5.665 nama unik dari 25.000 mahasiswa; 19.335 baris berbagi email pribadi dengan mahasiswa bernama sama. **Tindak lanjut: semua perhitungan wajib berbasis NIM.**
4. no_whatsapp kehilangan awalan nol di seluruh 25.000 baris; kolom hp di student_all masih benar dan angkanya identik. **Tindak lanjut: pakai kolom hp, atau tambahkan nol saat cleaning.**
5. sync_date berformat dd/mm/yyyy, beda dari tabel perusahaan. **Tindak lanjut: set format per kolom saat import.**

### Pertanyaan terbuka untuk meeting

1. Mahasiswa Available tanpa CV (1.448 orang) ditampilkan sebagai eligible penuh atau segmen "perlu melengkapi dokumen"?
2. Ketersediaan Placed tidak selalu didukung record Placement di tracking_student (4.163 kasus). Sumber kebenaran placement pakai yang mana?

---

## Findings: Sisi Tracking

Cluster milik Afrizal, diprofil awal oleh Andalan sebagai referensi.
Tanggal: 15 Juli 2026

### Ringkasan 3 kalimat

Relasi antar tabel utuh sempurna (0 orphan di semua foreign key) dan jumlah kiriman selalu konsisten antara jumlah_dikirimkan, isi list_nim, dan baris tracking_student. Temuan terbesar: kolom status rekap (tracking_company.progress) tidak sinkron dengan detail per mahasiswa, dan dua sumber placement (tracking_student vs ketersediaan) berselisih 4.163 mahasiswa. Aturan resmi FU dan Ghosting dari panitia terbukti konsisten dengan data, jadi bisa langsung dipakai sebagai logika deteksi.

### Bentuk data

| File | Baris | Kolom | Sesuai dokumentasi? |
|---|---|---|---|
| tracking_company.csv | 12.000 | 13 | Ya, panitia konfirmasi angka 14 di dokumentasi salah tulis |
| tracking_student.csv | 41.600 | 11 | Ya |

### Kontradiksi dan anomali

1. 3.135 dari 4.187 baris Closed (75%) masih punya mahasiswa di tahap aktif; 1.676 dari 1.778 baris Submitted (94%) anaknya justru sudah selesai. **Tindak lanjut: jangan pakai tracking_company.progress untuk funnel; konfirmasi di meeting.**
2. 2.578 dari 41.600 baris (6,2%): progress_student Finish tapi rejection On Progress. **Tindak lanjut: putuskan di meeting.** Opsi: (a) Finish dianggap final, kolom rejection diabaikan untuk baris ini; (b) baris ini dikeluarkan dari perhitungan keberhasilan dan dilaporkan sebagai data tidak lengkap.
3. 48 baris list_nim berisi satu NIM sah diikuti nilai "2" yang terpotong (contoh: "20211268,2"), kemungkinan hasil pemotongan angka panjang oleh spreadsheet. Panitia mengumumkan perbaikan list_nim, tapi file yang kami unduh masih identik byte per byte dengan versi lama (checksum sama) dan 48 baris ini masih ada. **Tindak lanjut: sudah ditangani, tidak perlu menunggu file panitia.** Untuk setiap baris rusak, tracking_student selalu punya tepat satu baris tambahan dengan id_tracking_company yang sama dan NIM yang hilang, jadi list_nim direkonstruksi lewat kode (kolom list_nim_perbaikan di notebook, CSV mentah tidak diedit). Seluruh 48 baris berhasil direkonstruksi tanpa ambiguitas. Untuk dashboard, tracking_student tetap jadi sumber kebenaran pengiriman per NIM; list_nim hanya referensi silang jumlah_dikirimkan. Kalau file resmi panitia terbit ulang, jalankan ulang cek ini.
4. 4.163 dari 9.301 mahasiswa berketersediaan Placed tidak punya record Placement; arah sebaliknya 0. **Tindak lanjut: putuskan sumber kebenaran placement di meeting.** Opsi: (a) tracking_student, lebih ketat dan bisa dirinci per perusahaan; (b) ketersediaan status_student, lebih besar tapi 45% tidak bisa dijelaskan.
5. 1.757 mahasiswa punya 2+ record Placement (maksimum 6). **Tindak lanjut: sepakati basis perhitungan, per orang atau per penempatan.**
6. Aturan resmi panitia untuk BT-05: ghosting berasal dari perusahaan, dihitung dari send_date (lebih dari 1 minggu FU 1, 2 minggu FU 2, 3 minggu FU 3, 4 minggu Ghosting). Tervalidasi: seluruh 2.905 baris Ghosting berumur lebih dari 4 minggu sejak send_date dan eskalasi FU terurut. **Tindak lanjut: pakai langsung sebagai logika deteksi ghosting di dashboard.**
7. internship_semester identik dengan semester terkini di seluruh 41.600 baris, jadi bukan catatan historis. **Tindak lanjut: rekap per periode pakai tanggal, bukan kolom ini.**
8. request_date dan send_date berformat dd/mm/yyyy. **Tindak lanjut: set format saat import.**
9. Pengiriman melebihi permintaan di 8.579 dari 12.000 baris (71,5%); dokumentasi menyebutnya buffer yang wajar. **Tindak lanjut: catat saja.**

### Pertanyaan terbuka untuk meeting

1. Sumber kebenaran placement: tracking_student atau status_student?
2. Perlakuan 2.578 baris Finish + On Progress?
3. Keberhasilan dihitung per orang atau per penempatan?
4. Urutan resmi tahapan funnel, terutama posisi Study Case dan CDC Briefing Student?
