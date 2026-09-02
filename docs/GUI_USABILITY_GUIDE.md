# MedRay GUI Usability Guide

Dokumen ini menerjemahkan prinsip human-factors dan usability workstation radiologi menjadi aturan praktis untuk MedRay v2. Tujuannya memudahkan penggunaan tanpa mengurangi fitur atau mengaburkan status keselamatan.

## Prinsip utama

1. **Task-first, feature-preserving**
   Fitur tetap tersedia, tetapi ditampilkan mengikuti tugas utama: `Import -> Route -> Review image -> Inspect AI signal -> Review annotation -> Draft report -> Export`. Fitur lanjutan berada di panel/tab yang konsisten, bukan dihapus.

2. **Study/image identity selalu terlihat**
   Case label, study, series, view, laterality, dan image aktif harus tetap terlihat di Reading Room, Result Cards, Report, DICOM Safety, dan Validation Workbench. Perubahan image aktif harus mengosongkan atau memuat ulang state yang relevan secara eksplisit.

3. **Staged disclosure**
   Tampilkan keputusan penting lebih dulu: kualitas image, routing anatomy, model aktif, confidence posture, review status, dan safe next action. Detail trace, metadata, dan evidence tetap tersedia melalui disclosure yang dapat dibuka.

4. **Status yang dapat dibedakan**
   Gunakan label dan warna berbeda untuk `demo/fallback`, `model signal`, `human reviewed`, `rejected`, `uncertain`, dan `validated for protocol`. Jangan mengandalkan warna saja; selalu sertakan teks atau ikon ber-label.

5. **Reversibility dan confirmation**
   Penghapusan case, clear-all, export de-identified DICOM, lock annotation, dan perubahan runtime harus memiliki konfirmasi atau status yang jelas. Operasi yang berisiko tidak boleh terjadi hanya karena klik pada area yang mudah salah.

6. **Keyboard dan target interaksi**
   Semua kontrol penting harus dapat dicapai keyboard, memiliki focus state yang terlihat, label yang bermakna, target sentuh yang cukup besar, dan alternatif untuk drag-only interaction. Shortcut boleh ditambahkan sebagai akselerator, bukan satu-satunya cara memakai fitur.

7. **Safety copy yang singkat dan dekat dengan tindakan**
   Gunakan kalimat langsung seperti `Grounding disabled: no reviewed localization artifact`, `Image is not DICOM`, atau `Export requires pixel review acknowledgement`. Hindari peringatan panjang yang terpisah dari tombol terkait.

## Baseline simplifikasi — 25 Agustus 2026

Baseline GUI saat ini menerapkan aturan berikut:

- Empat tujuan harian tetap terlihat: Dasbor, Ruang Baca, Library Kasus, dan Panduan. Validasi, Cari Model, Pengaturan AI, dan Tentang tetap tersedia di grup navigasi `Riset` yang dapat dibuka saat diperlukan.
- Header hanya menjelaskan tujuan halaman saat ini; disclaimer global tidak diulang di setiap header, tetapi status riset tetap terlihat dan safety copy tetap dekat dengan aksi berisiko.
- Kontrol yang belum dapat dipakai tidak memenuhi layar: toolbar image dan panel hasil Ruang Baca muncul setelah konteks yang diperlukan tersedia.
- Library memuat 15 kasus per batch, menghilangkan UUID dari tampilan utama, dan memindahkan clear-all ke `Kelola`.
- Metadata Validasi, setup/model teknis, direct download, dan katalog referensi tetap tersedia melalui disclosure atau tab yang dapat dibuka pengguna.
- Pengaturan AI memakai lapisan sederhana terlebih dahulu: `Default`, `Ollama`, atau `Compatible API`. Seluruh hardware advisor, model slots, adapters, registry, dan pengaturan riset lama tetap tersedia melalui `Advanced model tools`.
- Audit browser pada sembilan halaman di viewport sempit tidak menemukan horizontal overflow. Build produksi dan 14 tes frontend lulus. Ini adalah regression baseline, bukan validasi human-factors formal.

## Pola layar yang direkomendasikan

### Reading Room

- Header tetap: case label, `image n/m`, view/laterality, study/series identity, routing status.
- Kolom kiri: input/import dan metadata ringkas.
- Tengah: image viewer dan toolbar.
- Kolom kanan: tab bertingkat `AI Output`, `Result Cards`, `Annotations`, `Report`, `AI Chat`, `Trust`, `DICOM Safety`, `Roadmap`.
- Tambahkan progress step yang dapat diklik tanpa mengubah urutan kerja atau menyembunyikan panel lanjutan.
- Saat berpindah image, tampilkan status `not analyzed`, `analyzed / review`, atau `analysis failed` di navigator; jangan hanya mengubah gambar tanpa status.

### Result Cards dan Report

- Setiap card menampilkan `source`, `image identity`, `review status`, `confidence`, `evidence`, dan `next safe action` dalam urutan tetap.
- Tombol promosi ke report hanya aktif setelah status review sesuai aturan.
- Rejected/unreviewed output tetap dapat dilihat untuk provenance, tetapi tidak boleh terlihat seperti temuan report yang sudah disetujui.

### Model Finder dan Runtime Settings

- Anggap konfigurasi model sebagai fitur opsional: mode bawaan harus dapat digunakan tanpa setup.
- Minta hanya data yang dibutuhkan oleh mode terpilih. URL Ollama dan bantuan instalasi berada di disclosure; izin pengiriman data kasus ditampilkan dekat konfigurasi API.
- Pertahankan semua alat teknis melalui `Advanced model tools`; penyederhanaan berarti progressive disclosure, bukan penghapusan fitur.
- Pisahkan `discovered`, `imported`, `human reviewed`, `protocol validated`, dan `runtime eligible` sebagai status terpisah.
- Tampilkan alasan tombol `Use for ...` disabled tepat di dekat tombol.
- Untuk cloud-capable backend, tampilkan indikator data egress dan default local-only secara konsisten.

### DICOM Safety

- Ringkas risiko sebelum tombol export: patient tags, private tags, burned-in pixels, UID changes, dan source preservation.
- Preview perubahan menggunakan tiga kelompok: `removed`, `replaced/regenerated`, `retained`.
- Acknowledgement untuk burned-in/high-risk pixel review harus berada di area tombol export dan memakai boolean yang jelas.

## Checklist pengujian usability

- Pengguna baru dapat mengunggah satu image dan menemukan tombol analisis tanpa membaca dokumentasi panjang.
- Pengguna dapat membedakan image aktif dari thumbnail lain dalam kurang dari satu pandangan.
- Pengguna dapat menjawab “model apa yang aktif?”, “hasil ini berasal dari mana?”, dan “sudah direview atau belum?” tanpa membuka lebih dari satu panel tambahan.
- Pengguna tidak dapat salah mengekspor DICOM berisiko tinggi tanpa melihat alasan dan melakukan acknowledgement.
- Semua aksi utama dapat dilakukan dengan keyboard dan focus tidak hilang saat panel/tab berubah.
- Error menjelaskan tindakan pemulihan, bukan hanya exception mentah.
- Validasi dilakukan dengan skenario task dan diukur dengan waktu, error interaksi, completion rate, serta System Usability Scale (SUS); jangan hanya mengandalkan opini developer.

## Referensi

- FDA, *Applying Human Factors and Usability Engineering to Medical Devices*: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/applying-human-factors-and-usability-engineering-medical-devices
- Moise & Atkins, *Designing Better Radiology Workstations*: https://pmc.ncbi.nlm.nih.gov/articles/PMC3046708/
- *A review of existing and potential computer user interfaces for modern radiology*: https://pmc.ncbi.nlm.nih.gov/articles/PMC6108970/
- *Design Requirements for Radiology Workstations*: https://pmc.ncbi.nlm.nih.gov/articles/PMC3043976/
- W3C, *Web Content Accessibility Guidelines (WCAG) 2.2*: https://www.w3.org/TR/wcag/
- W3C, *Help Users Understand What Things Are and How to Use Them*: https://www.w3.org/WAI/WCAG2/supplemental/objectives/o1-understandable/
- GOV.UK, *Making your service look like GOV.UK* — mulai dari satu hal per halaman dan sederhanakan layanan: https://www.gov.uk/service-manual/design/making-your-service-look-like-govuk
- GOV.UK, *Structuring forms* — satu hal per halaman membantu fokus, pemahaman, mobile, dan pemulihan error: https://www.gov.uk/service-manual/design/form-structure
- Microsoft, *Progressive disclosure controls* — pertahankan status penting dan tampilkan detail saat diminta: https://learn.microsoft.com/en-us/windows/win32/uxguide/ctrl-progressive-disclosure-controls
- GOV.UK, *Details* — gunakan disclosure untuk informasi yang hanya dibutuhkan sebagian pengguna dan jangan sembunyikan informasi yang dibutuhkan mayoritas: https://design-system.service.gov.uk/components/details/
- Microsoft, *Wizards* — arahkan satu tugas utama, kurangi halaman opsional, dan tampilkan langkah lanjutan setelah prasyarat terpenuhi: https://learn.microsoft.com/en-us/windows/win32/uxguide/win-wizards

Dokumen ini adalah panduan desain dan usability untuk riset/prototyping; bukan pengganti validasi human-factors formal atau persyaratan regulatori.
