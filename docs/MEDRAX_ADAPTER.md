# MedRAX Adapter

MedRay v2 tidak menyalin MedRAX. Ia menyediakan adapter tipis agar tool eksternal bisa dipasang tanpa mengubah schema UI dan storage.

## Tujuan

- Menjaga output tetap terstruktur: findings, annotations, report, warnings, dan model trace.
- Membuat tiap tool bisa gagal secara eksplisit tanpa membuat hasil terlihat seperti diagnosis pasti.
- Memisahkan provenance koordinat: model-returned coordinate, segmentation mask, fallback heuristic, atau manual user annotation.
- Membuat annotation/grounding/segmentation menjadi bukti visual yang bisa direview, bukan hanya dekorasi overlay.
- Menyimpan runtime snapshot agar hasil bisa diaudit ulang.

## Komponen Lokal

- `MedRaxTool`: kontrak minimal untuk wrapper tool.
- `AgentOrchestrator`: menjalankan tool secara berurutan dan mengumpulkan trace.
- `OutputNormalizer`: menjaga hasil sesuai `AnalysisResult`.
- `RuntimeConfig`: memilih backend dan model per fungsi.
- `ModelMetadata`: target metadata untuk model card/registry.

## Tool Contract Yang Diinginkan

Wrapper tool sebaiknya menerima context berikut:

- `case_id`
- `image.stored_path`
- `image.preview_path`
- `image.metadata`
- `custom_prompt`
- `runtime`

Wrapper tool sebaiknya mengembalikan:

- `task_type`: classification, segmentation, grounding, vqa, report, utility.
- `status`: ok, fallback, skipped, failed.
- `model`: nama model aktual.
- `outputs`: payload mentah yang masih aman disimpan lokal.
- `normalized`: findings/annotations/report fields bila tersedia.
- `warnings`: keterbatasan model dan kondisi gagal.

Untuk tool annotation, grounding, atau segmentation, wrapper juga harus menyimpan:

- coordinate space: original image, preview image, atau model input.
- original image size dan model input size.
- transform metadata: resize, crop, padding, normalization.
- coordinate/mask provenance: bbox, polygon, mask path, mask checksum bila ada.
- relationship ke finding atau candidate diagnosis bila tersedia.

## Prioritas Integrasi

1. DICOM utility dan metadata validation.
2. CXR classifier dengan probabilitas dan calibration note.
3. Annotation review layer untuk provenance dan export overlay.
4. Grounding model hanya bila koordinat benar-benar berasal dari model.
5. Segmentation model hanya bila transform resize dan mask provenance ikut tersimpan.
6. Report generator yang memakai findings, candidate diagnosis, dan annotation refs terstruktur.
7. VQA/agent planner setelah tool deterministik cukup stabil.

## Referensi

- MedRAX repository: https://github.com/bowang-lab/MedRAX
- MedRAX paper: https://arxiv.org/abs/2502.02673
